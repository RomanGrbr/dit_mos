# Facebook Group Members Parser

Сбор открытых данных об участниках группы Facebook и REST API для доступа к ним.

(Так как в группе более 100000 участников, всех не собирал.
Пример выгруженных данных из elastic в фале response_example.json)

## Стек

- Python 3.11 / Django 4.2 / DRF
- PostgreSQL — сессии, состояние парсинга, пути к аватаркам
- Elasticsearch — полнотекстовый поиск и хранилище данных участников
- Celery + Redis — фоновые задачи
- `session.py` — захват сессии на хостовой машине (Selenium + Chrome)

## Архитектура

```
[Хост] session.py → session_data.json
    ↓ (volume)
[worker] capture_session  ← читает файл, сохраняет FacebookSession в БД
             ↓
         scrape_group      ← cursor-based HTTP пагинация участников → ES + PG
         enrich_members    ← HTTP hovercard → обогащение + скачивание аватарок
```

**Celery-задачи:**

| Задача | Очередь | Расписание |
|---|---|---|
| `capture_session` | `capture` | раз в сутки + по требованию |
| `scrape_group` | `celery` | каждые 3 мин |
| `enrich_members` | `celery` | каждые 5 мин |

## Быстрый старт

### 1. Захват сессии на хосте

Перед запуском закройте все окна Chrome с профилем Facebook.

Задайте путь к профилю пользователя в PROFILE_PATH скрипта session.py

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install selenium webdriver-manager
python session.py
```

Скрипт откроет Chrome, перехватит GraphQL-запрос участников и сохранит `session_data.json`.
Успешный вывод:

```
fb_dtsg: OK | lsd: OK | doc_id_members: 26296... | cookies: 28 | payload_params: 18 полей
Сессия сохранена в session_data.json
```

Если `doc_id_members: ПУСТО` — страница не успела загрузить участников, запустите повторно.

### 2. Настройка окружения

```bash
cp .env.example .env
```

Обязательные поля в `.env`:

```env
SECRET_KEY=...
GROUP_URL=https://www.facebook.com/groups/YOUR_GROUP
GROUP_ID=YOUR_GROUP_ID
POSTGRES_PASSWORD=postgres

# Прямой IP Facebook для GraphQL-запросов (обход блокировок/DNS)
FACEBOOK_IP=31.13.72.36

# Путь к session_data.json внутри контейнера
SESSION_DATA_PATH=/app/session_data.json
```

### 3. Прокси для воркера

Воркер работает в `network_mode: host` и скачивает аватарки через локальный прокси.
Если Facebook недоступен напрямую из контейнера — укажите прокси в `docker-compose.yml`
в секции `worker.environment`:

```yaml
- HTTPS_PROXY=http://127.0.0.1:12334   # порт вашего прокси (Hiddify, Clash, etc.)
- HTTP_PROXY=http://127.0.0.1:12334
- NO_PROXY=localhost,127.0.0.1,31.13.72.36
```

`FACEBOOK_IP` в `NO_PROXY` — чтобы GraphQL-запросы шли напрямую, минуя прокси.

### 4. Запуск

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
mkdir -p media/avatars && chmod 777 media/avatars
```

Запустить `capture_session` вручную (без ожидания расписания):

```bash
docker compose exec worker celery -A config call members.capture_session
```

## Обновление сессии

Сессия протухает ~раз в 12 часов. Признак в логах:

```
Файл сессии устарел (Xч > 12ч). Запустите session.py на хостовой машине.
```

Порядок: закрыть Chrome → `python session.py` → `capture_session` подхватит автоматически.

## REST API

Базовый URL: `http://localhost:8001`

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/members/` | Список участников с фильтрами и пагинацией |
| GET | `/api/members/{facebook_id}/` | Данные конкретного участника |
| GET | `/api/members/status/` | Разбивка по статусам обогащения |
| GET | `/api/members/stats/` | Общая статистика (ES, PG, обогащение) |
| GET | `/api/docs/` | Swagger UI |

**Фильтры для `/api/members/`:**

| Параметр | Значения | Описание |
|---|---|---|
| `search` | строка | Полнотекстовый поиск по имени, bio, username |
| `gender` | `male` / `female` | Пол |
| `is_verified` | `true` / `false` | Верифицированный аккаунт |
| `enrichment` | `all` / `enriched` / `pending` | Статус обогащения |
| `has_avatar` | `true` / `false` | Наличие скачанной аватарки |
| `scraped_at_from` | `YYYY-MM-DD` | Дата сбора — с |
| `scraped_at_to` | `YYYY-MM-DD` | Дата сбора — по |
| `page` / `page_size` | число | Пагинация |

## Структура проекта

```
session.py              — захват сессии на хосте
config/                 — настройки Django и Celery
members/
  models.py             — FacebookUser, FacebookSession, ParserState
  tasks.py              — capture_session, scrape_group, enrich_members
  views.py              — REST API
  es_client.py          — работа с Elasticsearch
scraper/
  group_scraper.py      — парсинг GraphQL-ответов
  graphql_client.py     — HTTP пагинация участников
  hovercard_client.py   — HTTP hovercard обогащение
  http_client.py        — базовый GraphQL клиент
Dockerfile              — образ для web и beat
docker-compose.yml
```
