import logging

from .group_scraper import parse_members
from .http_client import make_session, post_graphql

logger = logging.getLogger(__name__)

FRIENDLY_NAME = "GroupsCometMembersPageRootQueryRelayPreloader"


class GraphQLClient:

    def __init__(self, session):
        """session: экземпляр members.models.FacebookSession"""
        self.http, self.cookies_dict = make_session(session.cookies)
        self.fb_dtsg = session.fb_dtsg
        self.lsd = session.lsd
        self.doc_id = session.doc_id_members
        self.variables_tmpl = session.variables_members or {}
        self.payload_params = session.payload_params or {}

    def fetch_members(self, cursor: str | None = None) -> tuple[list[dict], str | None]:
        """
        Выполняет один HTTP POST к GraphQL.
        Возвращает (members, end_cursor). end_cursor=None если страниц больше нет.
        """
        variables = dict(self.variables_tmpl)
        variables["cursor"] = cursor

        data = post_graphql(
            self.http, self.cookies_dict,
            self.fb_dtsg, self.lsd,
            FRIENDLY_NAME, self.doc_id,
            variables,
            self.payload_params,
        )

        if not data:
            return [], None

        if not self.is_session_valid(data):
            logger.warning(f'Сессия невалидна: {str(data)[:200]}')
            return [], None

        members, end_cursor = parse_members(data)
        return members, end_cursor

    def is_session_valid(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        if data.get("errors"):
            return False
        if "data" not in data:
            return False
        return True
