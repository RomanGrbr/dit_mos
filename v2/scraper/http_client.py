"""
Базовый HTTP-клиент для запросов к Facebook GraphQL.
"""
import gzip
import json
import logging

import brotli
import requests
import urllib3
import zstandard as zstd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from django.conf import settings

logger = logging.getLogger(__name__)

GRAPHQL_URL = f"https://{settings.FACEBOOK_IP}/api/graphql/"


def decode_response(response) -> str:
    enc = response.headers.get('content-encoding', '').lower()
    content = response.content
    text = None

    if 'zstd' in enc:
        try:
            text = zstd.ZstdDecompressor().decompress(content, max_output_size=10 * 1024 * 1024).decode('utf-8')
        except Exception:
            pass

    if text is None and 'br' in enc:
        try:
            text = brotli.decompress(content).decode('utf-8')
        except Exception:
            pass

    if text is None and 'gzip' in enc:
        try:
            text = gzip.decompress(content).decode('utf-8')
        except Exception:
            pass

    if text is None:
        text = content.decode('utf-8', errors='replace')

    if text.startswith("for (;;);"):
        text = text[9:]
    return text


def cookies_list_to_dict(cookies_list: list) -> dict:
    """Конвертирует список cookies [{name, value, ...}] в простой dict {name: value}."""
    return {c["name"]: c["value"] for c in cookies_list}


def make_session(cookies_list: list) -> tuple[requests.Session, dict]:
    """Создаёт requests.Session с cookies. Возвращает (session, cookies_dict)."""
    cookies_dict = cookies_list_to_dict(cookies_list)
    http = requests.Session()
    http.cookies.update(cookies_dict)
    return http, cookies_dict


def build_payload(cookies_dict: dict, fb_dtsg: str, lsd: str,
                  friendly_name: str, doc_id: str, variables: dict,
                  payload_params: dict | None = None) -> dict:
    """
    Собирает полный payload для POST-запроса к GraphQL.
    payload_params — сессионно-специфичные поля захваченные session.py
    (__hs, __rev, __s, __hsi, __dyn, __spin_t и др.).
    Если не переданы, используются захардкоженные значения как fallback.
    """
    c_user = cookies_dict.get("c_user", "")
    result = {
        "__aaid": "0",
        "__a": "1",
        "__req": "q",
        "__hs": "20505.HYP:comet_pkg.2.1...0",
        "dpr": "1",
        "__ccg": "EXCELLENT",
        "__rev": "1033810692",
        "__s": "9e1811:djtyl3:1yc8mj",
        "__hsi": "7609111125999919327",
        "__dyn": "7xeUjGU5a5Q1ryaxG4Vp41twWwIxu13wFwhUKbgS3q2ibwNw9G2Saw8i2S1DwUx60GE3Qwb-q7oc81EEc87m221Fwgo9oO0n24oaEnxO0Bo7O2l2Utwqo5W1ywiE4u9x-3m1mzXw8W58jwGzEaE5e3ym2SU4i5oe8cEW4-5pUfEe88o4Wm7-2K0-obUG2-azqwt8eo88cA0Lo4q58jyUaUbGxe6Uak0zU8oC1Hg6C13xecwBwWzUlwEKufxamEbbxG1fBG2-0P8461wweW2K3abxG6E2Uw",
        "__csr": "",
        "__comet_req": "15",
        "jazoest": "25483",
        "__spin_r": "1033810692",
        "__spin_b": "trunk",
        "__spin_t": "1771634241",
        "__crn": "comet.fbweb.CometGroupMembersRoute",
        "qpl_active_flow_ids": "431626709",
        "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true",
        "fb_api_analytics_tags": '["qpl_active_flow_ids=431626709"]',
    }
    if payload_params:
        result.update(payload_params)
    result.update({
        "av": c_user,
        "__user": c_user,
        "fb_dtsg": fb_dtsg,
        "lsd": lsd,
        "fb_api_req_friendly_name": friendly_name,
        "variables": json.dumps(variables, separators=(',', ':')),
        "doc_id": doc_id,
    })
    return result


def build_headers(lsd: str, friendly_name: str) -> dict:
    return {
        "authority": "www.facebook.com",
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "host": "www.facebook.com",
        "origin": "https://www.facebook.com",
        "referer": f"https://www.facebook.com/groups/{settings.GROUP_ID}/members",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "x-fb-friendly-name": friendly_name,
        "x-fb-lsd": lsd,
        "x-asbd-id": "359341",
    }


def post_graphql(http: requests.Session, cookies_dict: dict,
                 fb_dtsg: str, lsd: str,
                 friendly_name: str, doc_id: str,
                 variables: dict,
                 payload_params: dict | None = None) -> dict:
    """Выполняет POST к GraphQL, возвращает распарсенный dict или {}."""
    payload = build_payload(cookies_dict, fb_dtsg, lsd, friendly_name, doc_id, variables, payload_params)
    headers = build_headers(lsd, friendly_name)
    try:
        resp = http.post(GRAPHQL_URL, headers=headers, data=payload, timeout=30, verify=False)
        text = decode_response(resp)
        logger.debug(f'[graphql] status={resp.status_code} len={len(text)}')
        return json.loads(text)
    except Exception:
        logger.exception('Ошибка post_graphql')
        return {}
