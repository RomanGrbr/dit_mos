import logging

from django.conf import settings

from .group_scraper import parse_hovercard
from .http_client import make_session, post_graphql

logger = logging.getLogger(__name__)

FRIENDLY_NAME = "CometHovercardQueryWrapper"


class HovercardClient:

    def __init__(self, session):
        """session: экземпляр members.models.FacebookSession"""
        self.http, self.cookies_dict = make_session(session.cookies)
        self.fb_dtsg = session.fb_dtsg
        self.lsd = session.lsd
        self.doc_id = session.doc_id_hovercard
        self.group_id = settings.GROUP_ID
        self.payload_params = session.payload_params or {}

    def enrich(self, facebook_id: str) -> dict | None:
        """
        Возвращает dict с данными hovercard или None если сессия протухла.
        Пустой dict {} если профиль закрыт.
        """
        data = post_graphql(
            self.http, self.cookies_dict,
            self.fb_dtsg, self.lsd,
            FRIENDLY_NAME, self.doc_id,
            {
                "actionBarRenderLocation": "WWW_COMET_HOVERCARD",
                "context": "DEFAULT",
                "entityID": facebook_id,
                "groupID": self.group_id,
                "scale": 1,
                "__relay_internal__pv__WorkCometIsEmployeeGKProviderrelayprovider": False,
            },
            self.payload_params,
        )

        if not data:
            return None

        if not self.is_session_valid(data):
            logger.warning(f'Сессия протухла для {facebook_id}')
            return None

        return parse_hovercard(data) or {}

    def is_session_valid(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        if data.get("__typename") == "XFBLoginRequired":
            return False
        if "data" not in data:
            return False
        for err in (data.get("errors") or []):
            msg = (err.get("message") or "").lower()
            if any(k in msg for k in ("login", "auth", "session", "unauthenticated")):
                return False
        return True
