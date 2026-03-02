from elasticsearch import Elasticsearch
from django.conf import settings

_client = None


def get_client() -> Elasticsearch:
    global _client
    if _client is None:
        _client = Elasticsearch(settings.ES_URL)
    return _client


ES_MAPPING = {
    "mappings": {
        "properties": {
            # Основные идентификаторы
            "facebook_id": {"type": "keyword"},
            "name": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256}
                }
            },
            "username": {"type": "keyword"},

            # URL-адреса (индексация не нужна, только хранение)
            "url": {"type": "keyword", "index": False},
            "profile_url": {"type": "keyword", "index": False},
            "group_member_url": {"type": "keyword", "index": False},
            "avatar": {"type": "keyword", "index": False},

            # Текстовые поля
            "bio": {"type": "text"},

            # Булевы флаги
            "is_verified":     {"type": "boolean"},
            "is_memorialized": {"type": "boolean"},
            "has_stories":     {"type": "boolean"},

            # Числовые поля
            "stories_count":          {"type": "integer"},
            "new_more_options_count": {"type": "integer"},
            "mutual_friends_count":   {"type": "integer"},

            # Взаимные друзья — только хранение, без индекса
            "mutual_friends_sample": {"type": "object", "enabled": False},

            # Контекстные строки из timeline (работа, учёба, город)
            "context_items": {"type": "text"},

            # Статусы и категории
            "friendship_status": {"type": "keyword"},
            "invite_status":     {"type": "keyword"},
            "user_type":         {"type": "keyword"},
            "gender":            {"type": "keyword"},

            # Имя для отображения (короткая версия)
            "short_name": {"type": "keyword"},

            # Даты (строкой, как приходят)
            "join_date": {"type": "keyword"},

            # Временные метки
            "scraped_at": {
                "type": "date",
                "format": "strict_date_time||strict_date_optional_time||epoch_millis"
            },
            "enriched_at": {
                "type": "date",
                "format": "strict_date_time||strict_date_optional_time||epoch_millis"
            },
        }
    }
}


def create_index() -> bool:
    client = get_client()
    if not client.indices.exists(index=settings.ES_INDEX):
        client.indices.create(index=settings.ES_INDEX, body=ES_MAPPING)
        return True
    return False


def index_member(data: dict):
    get_client().index(
        index=settings.ES_INDEX,
        id=data['facebook_id'],
        document=data,
    )


def update_member(facebook_id: str, fields: dict):
    get_client().update(
        index=settings.ES_INDEX,
        id=facebook_id,
        doc=fields,
        doc_as_upsert=True,
        retry_on_conflict=3,
    )


def get_member(facebook_id: str) -> dict | None:
    result = get_client().get(index=settings.ES_INDEX, id=facebook_id, ignore=404)
    if result.get('found'):
        return result['_source']
    return None


def search_members(query: dict) -> dict:
    return get_client().search(index=settings.ES_INDEX, body=query)


def count_index() -> int:
    return get_client().count(index=settings.ES_INDEX)['count']
