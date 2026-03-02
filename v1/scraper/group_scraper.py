"""
Парсинг GraphQL-ответов Facebook: участники группы и hovercard.
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def parse_members(data: dict) -> tuple[list[dict], str | None]:
    """
    Парсит участников из GraphQL-ответа.
    Возвращает (members, end_cursor). end_cursor=None если страниц больше нет.
    """
    members = []
    end_cursor = None
    try:
        nm        = data["data"]["node"]["new_members"]
        edges     = nm.get("edges", [])
        page_info = nm.get("page_info", {})
        if page_info.get("has_next_page"):
            end_cursor = page_info.get("end_cursor")
    except (KeyError, TypeError):
        return members, end_cursor

    scraped_at = datetime.now(timezone.utc).isoformat()
    for edge in edges:
        node  = edge.get("node", {})
        fb_id = node.get("id", "")
        if not fb_id:
            continue
        utr     = node.get("user_type_renderer") or {}
        signals = ((node.get("group_membership") or {}).get("user_signals_info") or {})
        members.append({
            "facebook_id":       fb_id,
            "name":              node.get("name", ""),
            "url":               node.get("url", ""),
            "avatar":            (node.get("profile_picture") or {}).get("uri", ""),
            "bio":               (node.get("bio_text") or {}).get("text", ""),
            "is_verified":       node.get("is_verified", False),
            "join_date":         (edge.get("join_status_text") or {}).get("text", ""),
            "invite_status":     (edge.get("invite_status_text") or {}).get("text", ""),
            "user_type":         utr.get("__typename", ""),
            "friendship_status": (utr.get("user") or {}).get("friendship_status", ""),
            "group_member_url":  signals.get("overflow_uri", ""),
            "scraped_at":        scraped_at,
        })
    return members, end_cursor


def parse_hovercard(data: dict) -> dict:
    """
    Парсит данные из Facebook hovercard.
    """
    try:
        user = data["data"]["node"]["comet_hovercard_renderer"]["user"]
    except (KeyError, TypeError):
        return {}

    result = {
        "facebook_id":     user.get("id"),
        "name":            user.get("name"),
        "username":        user.get("username_for_profile") or "",
        "is_verified":     user.get("is_verified", False),
        "is_memorialized": user.get("is_visibly_memorialized", False),
        "profile_url":     user.get("profile_url") or user.get("url") or "",
        "avatar":          (user.get("profile_picture") or {}).get("uri") or "",
        "short_name":      None,
        "gender":          None,
        "friendship_status": None,
    }

    for action in (user.get("primaryActions") or []):
        handler        = (action.get("client_handler") or {})
        profile_action = (handler.get("profile_action") or {})
        atype          = action.get("profile_action_type") or action.get("__typename") or ""

        if atype in ("FRIEND", "ProfileActionFriendRequest"):
            owner = (profile_action.get("restrictable_profile_owner") or {})
            result["friendship_status"] = owner.get("friendship_status")
            result["gender"]            = owner.get("gender")
            result["short_name"]        = owner.get("short_name")

        elif atype in ("MESSAGE", "ProfileActionMessage"):
            owner = (profile_action.get("profile_owner") or {})
            if not result["gender"]:
                result["gender"]     = owner.get("gender")
            if not result["short_name"]:
                result["short_name"] = owner.get("short_name")

    context_items = []
    mutual_count  = 0
    mutual_sample = []

    for node in (user.get("timeline_context_items") or {}).get("nodes", []):
        title = node.get("title") or {}
        text  = (title.get("text") or "").strip()
        if text:
            context_items.append(text)

        for agg in (title.get("aggregated_ranges") or []):
            if agg.get("count"):
                mutual_count  = agg["count"]
                mutual_sample = [
                    {"id": e["id"], "name": e["name"]}
                    for e in (agg.get("sample_entities") or [])
                    if e.get("id")
                ]

    result["context_items"] = context_items
    if mutual_count:
        result["mutual_friends_count"]  = mutual_count
        result["mutual_friends_sample"] = mutual_sample

    return result
