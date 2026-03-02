"""
Открывает Chrome под авторизованным профилем Facebook, переходит на страницу
участников группы, перехватывает GraphQL-запросы и сохраняет параметры сессии
в session_data.json.

Требования:
    pip install selenium webdriver-manager

Перед запуском:
    1. Убедитесь, что PROFILE_PATH указывает на Chrome-профиль с авторизацией FB
    2. Закройте все окна Chrome с этим профилем (иначе профиль заблокирован)
    3. Запустите: python session.py
"""
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv(Path(__file__).parent / '.env')

# ── Настройки ─────────────────────────────────────────────────────────────────
PROFILE_PATH = os.getenv('CHROME_PROFILE_PATH', '/home/roman/.config/google-chrome/Default')
GROUP_URL = os.getenv('GROUP_URL', 'https://www.facebook.com/groups/CrimeaBeauty')
OUTPUT_FILE = Path(os.getenv('SESSION_DATA_PATH', str(Path(__file__).parent / 'session_data.json')))
PAGE_WAIT = int(os.getenv('SESSION_PAGE_WAIT', '5'))

# Поля которые НЕ идут в payload_params: они либо per-request, либо хранятся отдельно
_EXCLUDE = {
    'fb_dtsg', 'lsd', 'doc_id', 'variables',
    'fb_api_req_friendly_name', 'av', '__user', 'fb_api_analytics_tags',
}
# ─────────────────────────────────────────────────────────────────────────────


def create_driver(profile_path: str) -> webdriver.Chrome:
    options = Options()
    options.add_argument(f'--user-data-dir={profile_path}')
    options.add_argument('--profile-directory=Default')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd('Network.enable', {})
    return driver


def capture_graphql(driver) -> list[tuple[dict, dict, dict]]:
    """
    Читает CDP performance-лог.
    Возвращает список (response_body, request_params, payload_params):
      - request_params: fb_dtsg, lsd, doc_id, variables
      - payload_params: все остальные поля POST-тела (сессионно-специфичные)
    """
    results = []
    for entry in driver.get_log('performance'):
        msg = json.loads(entry['message'])['message']
        if msg['method'] != 'Network.responseReceived':
            continue
        url = msg['params']['response'].get('url', '')
        if '/api/graphql/' not in url:
            continue

        request_id = msg['params']['requestId']

        try:
            body_raw = driver.execute_cdp_cmd(
                'Network.getResponseBody', {'requestId': request_id}
            ).get('body', '')
            if body_raw.startswith('for (;;);'):
                body_raw = body_raw[9:]
            response_body = json.loads(body_raw)
        except Exception:
            continue

        request_params = {}
        payload_params = {}
        try:
            post_data = driver.execute_cdp_cmd(
                'Network.getRequestPostData', {'requestId': request_id}
            ).get('postData', '')
            parsed = parse_qs(post_data)

            request_params = {
                'fb_dtsg': parsed.get('fb_dtsg', [''])[0],
                'lsd': parsed.get('lsd', [''])[0],
                'doc_id': parsed.get('doc_id', [''])[0],
            }
            try:
                request_params['variables'] = json.loads(
                    parsed.get('variables', ['{}'])[0]
                )
            except Exception:
                request_params['variables'] = {}

            # Все остальные поля — сессионно-специфичные параметры для build_payload
            for key, values in parsed.items():
                if key not in _EXCLUDE and values:
                    payload_params[key] = values[0]

        except Exception:
            pass

        results.append((response_body, request_params, payload_params))
    return results


def find_members_entry(entries):
    """
    Ищет запрос с new_members в ответе.
    Возвращает (request_params, payload_params) или (None, None).
    """
    for response_body, request_params, payload_params in entries:
        try:
            response_body['data']['node']['new_members']
            return request_params, payload_params
        except (KeyError, TypeError):
            continue
    return None, None


def main() -> None:
    members_url = GROUP_URL.rstrip('/') + '/members'
    print(f'Профиль: {PROFILE_PATH}')
    print(f'Цель: {members_url}')
    print(f'Вывод: {OUTPUT_FILE}')
    print('Запускаем Chrome...')

    driver = create_driver(PROFILE_PATH)
    try:
        driver.get(members_url)
        print(f'Страница загружается: {driver.title!r}')
        print(f'Ждём {PAGE_WAIT} сек...')
        time.sleep(PAGE_WAIT)

        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(3)

        entries = capture_graphql(driver)
        print(f'GraphQL-ответов перехвачено: {len(entries)}')

        request_params, payload_params = find_members_entry(entries)

        session_data = {
            'cookies': driver.get_cookies(),
            'fb_dtsg': '',
            'lsd': '',
            'doc_id_members': '',
            'variables_members': {},
            'payload_params': {},
        }

        if request_params:
            session_data['fb_dtsg'] = request_params.get('fb_dtsg', '')
            session_data['lsd'] = request_params.get('lsd', '')
            session_data['doc_id_members'] = request_params.get('doc_id', '')
            session_data['variables_members'] = request_params.get('variables', {})
            session_data['payload_params'] = payload_params
            print(f'Найден members-запрос: doc_id={session_data["doc_id_members"]!r}')
            print(f'payload_params: {len(payload_params)} полей: {list(payload_params.keys())}')
        else:
            for _, params, pp in entries:
                if params.get('fb_dtsg'):
                    session_data['fb_dtsg'] = params['fb_dtsg']
                    session_data['payload_params'] = pp
                if params.get('lsd'):
                    session_data['lsd'] = params['lsd']
            print('ВНИМАНИЕ: members-запрос не найден. Попробуйте прокрутить страницу вручную.')

        print(
            f'fb_dtsg: {"OK" if session_data["fb_dtsg"] else "ПУСТО"} | '
            f'lsd: {"OK" if session_data["lsd"] else "ПУСТО"} | '
            f'doc_id_members: {session_data["doc_id_members"] or "ПУСТО"} | '
            f'cookies: {len(session_data["cookies"])} | '
            f'payload_params: {len(session_data["payload_params"])} полей'
        )

        OUTPUT_FILE.write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f'\nСессия сохранена в {OUTPUT_FILE}')

        print('\nНажмите Enter для закрытия браузера...')
        input()
    finally:
        driver.quit()
        print('Браузер закрыт.')


if __name__ == '__main__':
    main()
