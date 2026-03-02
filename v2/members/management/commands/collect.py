"""
Последовательный сбор и обогащение участников группы Facebook.

Запуск:  python manage.py collect
При повторном запуске продолжает с сохранённого курсора.
"""
import json
import logging
import random
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from members.models import FacebookUser, FacebookSession, ParserState

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Последовательный сбор и обогащение участников группы'

    def handle(self, *args, **kwargs):
        logger.info('Запуск сборщика')

        session = self._ensure_session()
        if session is None:
            logger.error('Не удалось получить сессию. Выход.')
            return

        state, _ = ParserState.objects.get_or_create(
            group_id=settings.GROUP_ID,
            defaults={'next_cursor': None, 'is_finished': False},
        )

        if state.is_finished:
            logger.info('Сбор уже завершён (is_finished=True). Выход.')
            return

        logger.info('Начало сбора. Курсор: %s', 'начало' if not state.next_cursor else 'продолжение')
        logger.info('Обогащение (ENRICH_ENABLED): %s', settings.ENRICH_ENABLED)

        from scraper.graphql_client import GraphQLClient

        iteration = 0
        gql = GraphQLClient(session)

        while not state.is_finished:
            iteration += 1
            logger.info('Итерация %d | cursor=%s', iteration, bool(state.next_cursor))

            # ── Сбор одного батча ──────────────────────────────────────────────
            members, end_cursor = gql.fetch_members(cursor=state.next_cursor)

            if not members and end_cursor is None:
                logger.warning('Пустой ответ — сессия протухла. Обновляем...')
                session = self._refresh_session()
                if session is None:
                    logger.error('Не удалось обновить сессию. Выход.')
                    return
                gql = GraphQLClient(session)
                continue

            saved_ids = []
            for m in members:
                try:
                    self._save_scraped(m)
                    saved_ids.append(m['facebook_id'])
                except Exception:
                    logger.exception('Ошибка сохранения %s', m.get('facebook_id'))

            logger.info('Сохранено %d участников', len(saved_ids))

            if end_cursor is None:
                state.is_finished = True
                state.next_cursor = None
            else:
                state.next_cursor = end_cursor
            state.save()

            # ── Обогащение того же батча ───────────────────────────────────────
            if saved_ids and settings.ENRICH_ENABLED:
                from scraper.hovercard_client import HovercardClient
                hc = HovercardClient(session)
                for fb_id in saved_ids:
                    try:
                        user = FacebookUser.objects.get(facebook_id=fb_id)
                        if user.enrich_status != FacebookUser.EnrichStatus.PENDING:
                            continue

                        user.enrich_attempts += 1
                        user.save(update_fields=['enrich_attempts'])

                        hc_data = hc.enrich(fb_id)

                        if hc_data is None:
                            logger.warning('Сессия протухла на обогащении %s. Обновляем...', fb_id)
                            session = self._refresh_session()
                            if session is None:
                                logger.error('Не удалось обновить сессию. Выход.')
                                return
                            hc = HovercardClient(session)
                            hc_data = hc.enrich(fb_id)  # одна повторная попытка

                        if hc_data is None:
                            FacebookUser.objects.filter(facebook_id=fb_id).update(
                                enrich_status=FacebookUser.EnrichStatus.FAILED
                            )
                        elif not hc_data:
                            user.enrich_status = FacebookUser.EnrichStatus.CLOSED
                            user.save(update_fields=['enrich_status'])
                        else:
                            self._apply_hovercard(user, hc_data)

                    except Exception:
                        logger.exception('Ошибка обогащения %s', fb_id)
                        FacebookUser.objects.filter(facebook_id=fb_id).update(
                            enrich_status=FacebookUser.EnrichStatus.FAILED
                        )

                    time.sleep(random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX))

            if not state.is_finished:
                time.sleep(random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX))

        logger.info('Сбор завершён! Итераций: %d', iteration)

    # ── Вспомогательные методы ────────────────────────────────────────────────

    def _save_scraped(self, data: dict):
        FacebookUser.objects.update_or_create(
            facebook_id=data['facebook_id'],
            defaults={
                'name':             data.get('name') or '',
                'url':              data.get('url') or '',
                'avatar_url':       data.get('avatar') or '',
                'bio':              data.get('bio') or '',
                'is_verified':      data.get('is_verified', False),
                'join_date':        data.get('join_date') or '',
                'invite_status':    data.get('invite_status') or '',
                'user_type':        data.get('user_type') or '',
                'friendship_status': data.get('friendship_status') or '',
                'group_member_url': data.get('group_member_url') or '',
            },
        )

    def _apply_hovercard(self, user: FacebookUser, hc_data: dict):
        avatar_url  = hc_data.get('avatar') or ''
        avatar_path = _download_avatar(user.facebook_id, avatar_url)

        user.username        = hc_data.get('username') or ''
        user.is_verified     = hc_data.get('is_verified', user.is_verified)
        user.is_memorialized = hc_data.get('is_memorialized', False)
        user.profile_url     = hc_data.get('profile_url') or ''
        if avatar_url:
            user.avatar_url  = avatar_url
        user.avatar_path     = avatar_path
        user.short_name      = hc_data.get('short_name') or ''
        user.gender          = hc_data.get('gender') or ''
        if hc_data.get('friendship_status'):
            user.friendship_status = hc_data['friendship_status']
        user.context_items         = hc_data.get('context_items') or []
        user.mutual_friends_count  = hc_data.get('mutual_friends_count')
        user.mutual_friends_sample = hc_data.get('mutual_friends_sample') or []
        user.enrich_status = FacebookUser.EnrichStatus.DONE
        user.enriched_at   = timezone.now()
        user.save()

    def _ensure_session(self) -> FacebookSession | None:
        """Возвращает существующую сессию из БД, иначе загружает из файла или запускает session.py."""
        try:
            return FacebookSession.objects.latest('updated_at')
        except FacebookSession.DoesNotExist:
            pass
        return self._load_session_from_file() or self._run_session_py()

    def _refresh_session(self) -> FacebookSession | None:
        """Запускает session.py и загружает новую сессию."""
        return self._run_session_py()

    def _run_session_py(self) -> FacebookSession | None:
        session_py = Path(settings.BASE_DIR) / 'session.py'
        logger.info('Запуск session.py: %s', session_py)
        result = subprocess.run([sys.executable, str(session_py)])
        if result.returncode != 0:
            logger.error('session.py завершился с кодом %d', result.returncode)
        return self._load_session_from_file()

    def _load_session_from_file(self) -> FacebookSession | None:
        path = Path(settings.SESSION_DATA_PATH)
        if not path.exists():
            logger.error('Файл сессии не найден: %s', path)
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            logger.exception('Ошибка чтения файла сессии')
            return None
        if not data.get('fb_dtsg') or not data.get('cookies'):
            logger.error('Файл сессии пустой или некорректный')
            return None
        session = FacebookSession.objects.create(
            cookies           = data['cookies'],
            fb_dtsg           = data['fb_dtsg'],
            lsd               = data.get('lsd', ''),
            doc_id_members    = data.get('doc_id_members') or settings.MEMBERS_DOC_ID,
            doc_id_hovercard  = settings.HOVERCARD_DOC_ID,
            variables_members = data.get('variables_members') or {},
            payload_params    = data.get('payload_params') or {},
        )
        logger.info('Сессия загружена из файла (id=%d)', session.pk)
        return session


def _download_avatar(fb_id: str, url: str) -> str | None:
    if not url:
        return None
    try:
        resp = requests.get(
            url,
            timeout=5,
            headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0'},
            verify=False,
        )
        if not resp.ok or 'image' not in resp.headers.get('content-type', ''):
            return None
        avatars_dir = Path(settings.AVATARS_DIR)
        avatars_dir.mkdir(parents=True, exist_ok=True)
        path = avatars_dir / f'{uuid4().hex}.jpg'
        path.write_bytes(resp.content)
        return str(path)
    except requests.exceptions.RequestException as e:
        logger.warning('Аватарка %s: не удалось загрузить — %s', fb_id, e)
        return None
    except Exception:
        logger.exception('Аватарка %s: непредвиденная ошибка', fb_id)
        return None
