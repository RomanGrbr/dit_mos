import json
import logging
import random
import time
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from uuid import uuid4

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import FacebookUser, FacebookSession, ParserState
from .es_client import index_member, update_member

logger = logging.getLogger(__name__)


def save_member(data: dict):
    """Индексирует участника в ES и создаёт запись FacebookUser в БД."""
    index_member(data)
    FacebookUser.objects.get_or_create(facebook_id=data['facebook_id'])


def _download_avatar(fb_id: str, url: str, http: requests.Session | None = None) -> str | None:
    """Загружает аватарку по URL и сохраняет в AVATARS_DIR."""
    logger.info(f'Аватарка {fb_id}: URL={url!r}')
    if not url:
        logger.warning(f'Аватарка {fb_id}: URL пустой')
        return None
    requester = http or requests
    try:
        resp = requester.get(
            url,
            timeout=5,
            headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0'},
            verify=False,
        )
        content_type = resp.headers.get('content-type', '')
        if not resp.ok or 'image' not in content_type:
            return None
        avatars_dir = Path(settings.AVATARS_DIR)
        avatars_dir.mkdir(parents=True, exist_ok=True)
        path = avatars_dir / f'{uuid4().hex}.jpg'
        path.write_bytes(resp.content)
        return str(path)
    except requests.exceptions.Timeout:
        logger.warning(f'Аватарка {fb_id}: таймаут при загрузке')
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f'Аватарка {fb_id}: не удалось загрузить — {e}')
        return None
    except Exception:
        logger.exception(f'Аватарка {fb_id}: непредвиденная ошибка')
        return None


def _get_session() -> FacebookSession | None:
    """
    Возвращает последнюю FacebookSession или None.
    При отсутствии сессии запускает capture_session_task и возвращает None.
    """
    try:
        return FacebookSession.objects.latest('updated_at')
    except FacebookSession.DoesNotExist:
        logger.warning('FacebookSession не найдена — запускаем capture_session_task')
        capture_session_task.delay()
        return None


@shared_task(name='members.capture_session')
def capture_session_task():
    """
    Загружает данные сессии из SESSION_DATA_PATH (файл создаётся скриптом
    session.py на хостовой машине и монтируется в контейнер через volume).

    Если файл отсутствует или устарел — логирует ошибку: оператор должен
    вручную запустить session.py и обновить файл.
    """
    path = Path(settings.SESSION_DATA_PATH)

    if not path.exists():
        logger.error(
            f'Файл сессии не найден: {path}. '
            'Запустите session.py на хостовой машине.'
        )
        return

    age_hours = (
        datetime.now(dt_timezone.utc)
        - datetime.fromtimestamp(path.stat().st_mtime, tz=dt_timezone.utc)
    ).total_seconds() / 3600

    if age_hours > settings.SESSION_MAX_AGE_HOURS:
        logger.error(
            f'Файл сессии устарел ({age_hours:.1f}ч > {settings.SESSION_MAX_AGE_HOURS}ч). '
            'Запустите session.py на хостовой машине.'
        )
        return

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        logger.exception(f'Ошибка чтения файла сессии: {path}')
        return

    if not data.get('fb_dtsg') or not data.get('cookies'):
        logger.error('Файл сессии пустой или некорректный. Запустите session.py повторно.')
        return

    fb_session = FacebookSession.objects.create(
        cookies=data['cookies'],
        fb_dtsg=data['fb_dtsg'],
        lsd=data.get('lsd', ''),
        doc_id_members=data.get('doc_id_members') or settings.MEMBERS_DOC_ID,
        doc_id_hovercard=settings.HOVERCARD_DOC_ID,
        variables_members=data.get('variables_members') or {},
        payload_params=data.get('payload_params') or {},
    )
    ParserState.objects.get_or_create(
        group_id=settings.GROUP_ID,
        defaults={'next_cursor': None, 'is_finished': False},
    )
    logger.info(f'Сессия загружена из файла (id={fb_session.pk}, возраст={age_hours:.1f}ч), запускаем scrape_group')
    scrape_group_task.delay()


@shared_task(name='members.scrape_group')
def scrape_group_task(batch_size: int = 50):
    """
    HTTP cursor-based пагинация участников.
    Берёт cursor из ParserState, делает batch_size запросов, обновляет cursor.
    """
    from scraper.graphql_client import GraphQLClient

    try:
        state = ParserState.objects.get(group_id=settings.GROUP_ID)
    except ParserState.DoesNotExist:
        logger.warning('ParserState не найден — запускаем capture_session_task')
        capture_session_task.delay()
        return

    if state.is_finished:
        logger.info('Парсинг завершён (is_finished=True)')
        return

    fb_session = _get_session()
    if fb_session is None:
        return

    client = GraphQLClient(fb_session)
    cursor = state.next_cursor
    total_saved = 0

    logger.info(f'Старт скрапинга. cursor={"продолжаем" if cursor else "с начала"}, batch_size={batch_size}')

    for i in range(batch_size):
        members, end_cursor = client.fetch_members(cursor=cursor)

        logger.info(f'Запрос {i+1}: получено {len(members)} участников, next_cursor={end_cursor is not None}')

        if not members and end_cursor is None:
            logger.warning('Пустой ответ или сессия протухла — запускаем capture_session_task')
            capture_session_task.delay()
            return

        for m in members:
            try:
                save_member(m)
                total_saved += 1
            except Exception:
                logger.exception(f'Ошибка сохранения {m["facebook_id"]}')

        cursor = end_cursor

        if end_cursor is None:
            state.is_finished = True
            state.next_cursor = None
            state.save()
            logger.info(f'Парсинг завершён. Всего сохранено: {total_saved}')
            return

        time.sleep(random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX))

    state.next_cursor = cursor
    state.save()
    logger.info(f'Батч завершён. Сохранено: {total_saved}, cursor для следующего запуска: {cursor is not None}')


@shared_task(name='members.enrich_members')
def enrich_members_task(batch_size: int = 50):
    """
    Обогащает pending-участников через HTTP hovercard запросы.
    """
    from scraper.hovercard_client import HovercardClient

    fb_session = _get_session()
    if fb_session is None:
        return

    if not fb_session.doc_id_hovercard:
        logger.warning('doc_id_hovercard не заполнен')
        return

    pending = list(
        FacebookUser.objects
        .filter(enrich_status=FacebookUser.EnrichStatus.PENDING, enrich_attempts__lt=3)
        .values_list('facebook_id', flat=True)[:batch_size]
    )

    if not pending:
        state = ParserState.objects.filter(group_id=settings.GROUP_ID, is_finished=False).first()
        if state:
            logger.info('Нет участников для обогащения — скрапинг ещё не завершён, запускаем scrape_group')
            scrape_group_task.delay()
        else:
            logger.info('Нет участников для обогащения')
        return

    client = HovercardClient(fb_session)
    logger.info(f'Обогащаем {len(pending)} участников')

    total_done   = 0
    total_closed = 0
    total_failed = 0

    for fb_id in pending:
        try:
            member = FacebookUser.objects.get(facebook_id=fb_id)
            member.enrich_attempts += 1
            member.save(update_fields=['enrich_attempts'])

            hc_data = client.enrich(fb_id)

            if hc_data is None:
                logger.warning(
                    f'Сессия протухла на {fb_id} (попытка {member.enrich_attempts}) '
                    f'— запускаем capture_session_task'
                )
                if member.enrich_attempts == 1:
                    # Запускаем захват только при первом признаке протухания
                    capture_session_task.delay()
                return

            if not hc_data:
                member.enrich_status = FacebookUser.EnrichStatus.CLOSED
                member.save(update_fields=['enrich_status'])
                total_closed += 1
            else:
                hc_data['enriched_at'] = timezone.now().isoformat()
                update_member(fb_id, hc_data)
                member.enrich_status = FacebookUser.EnrichStatus.DONE
                member.enriched_at   = timezone.now()
                avatar_url = hc_data.get('avatar') or ''
                #TODO Есть вероятность что ссылки на аватрки протухнут,
                # тогда стоит перенести загрузку в scrape_group_task
                member.avatar_path = _download_avatar(fb_id, avatar_url, http=client.http)
                member.save(update_fields=['enrich_status', 'enriched_at', 'avatar_path'])
                total_done += 1

        except Exception:
            logger.exception(f'Ошибка обогащения для {fb_id}')
            FacebookUser.objects.filter(facebook_id=fb_id).update(
                enrich_status=FacebookUser.EnrichStatus.FAILED
            )
            total_failed += 1

        time.sleep(random.uniform(settings.REQUEST_DELAY_MIN, settings.REQUEST_DELAY_MAX))

    logger.info(
        f'Батч обогащения завершён. Обогащено: {total_done}, '
        f'закрытых профилей: {total_closed}, ошибок: {total_failed}, '
        f'из {len(pending)}'
    )
