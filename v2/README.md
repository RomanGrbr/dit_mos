# Facebook Group Members Parser

Инструмент для сбора и обогащения данных участников закрытой группы Facebook.
Собирает участников через GraphQL API, обогащает профили через hovercard, сохраняет в SQLite.

## Стек

| Компонент | Технология |
|---|---|
| Веб-фреймворк | Django 4.2 + Django REST Framework |
| База данных | SQLite |
| API-документация | drf-spectacular (Swagger) |
| Фильтрация | django-filter |
| Захват сессии | Selenium + Google Chrome |
| HTTP-запросы | requests + brotli + zstandard |

---

### ВАЖНО!!!

Я не обходил авторизацию и капчу, сбор выполняется под авторизованной сессией.
Установите Google Chrome, авторизуйтесь в facebook, укажите путь к Chrome-профилю CHROME_PROFILE_PATH, настройте HTTPS_PROXY
При необходимости ускорить процесс(раз в 10), можно отключить обогащение данных участников из hover.

## Требования к системе

- **ОС**: Linux (Ubuntu 20.04+, Debian 11+)
- **Python**: 3.11+
- **Google Chrome**: обязательно установлен и авторизован в Facebook

### Установка Google Chrome

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

> ChromeDriver устанавливается автоматически через `webdriver-manager` при первом запуске `session.py`.

---

## Настройка

### 1. Виртуальное окружение и зависимости

```bash
cd v3
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Файл `.env`

```bash
cp .env.example .env
```

Отредактируйте `.env`. Обязательные параметры:

| Параметр | Описание | Пример |
|---|---|---|
| `GROUP_URL` | URL страницы участников группы | `https://www.facebook.com/groups/CrimeaBeauty` |
| `GROUP_ID` | Числовой ID группы Facebook | `1883332381741292` |
| `HOVERCARD_DOC_ID` | doc_id для hovercard GraphQL-запроса | `33705242655757750` |
| `CHROME_PROFILE_PATH` | Путь к Chrome-профилю с авторизацией FB | `/home/user/.config/google-chrome/Default` |

> **Где взять `GROUP_ID`**: откройте исходный код страницы группы и найдите `"groupID"`.
> **Где взять `HOVERCARD_DOC_ID`**: откройте DevTools → Network, откройте профиль любого участника через hovercard, найдите запрос к `/api/graphql/` с `fb_api_req_friendly_name=CometHovercardQueryWrapper` и скопируйте `doc_id`.

Дополнительные параметры:

| Параметр | Описание | По умолчанию |
|---|---|---|
| `ENRICH_ENABLED` | Включить обогащение через hovercard | `true` |
| `BATCH_SIZE` | Участников за один GraphQL-запрос | `10` |
| `REQUEST_DELAY_MIN` / `REQUEST_DELAY_MAX` | Задержка между запросами (сек) | `1.0` / `2.0` |
| `SESSION_PAGE_WAIT` | Ожидание загрузки страницы в session.py (сек) | `5` |
| `SESSION_DATA_PATH` | Путь к файлу сессии | `session_data.json` |
| `AVATARS_DIR` | Директория для аватарок | `media/avatars` |
| `HTTPS_PROXY` / `HTTP_PROXY` | Прокси для загрузки аватарок | — |

### 3. Захват сессии Facebook

Запускать `session.py` вручную **не обязательно**. При первом старте сборщик сам обнаружит отсутствие сессии и автоматически запустит его. То же происходит при протухании сессии в процессе сбора.

Когда откроется браузер — дождитесь загрузки страницы участников и нажмите **Enter** для закрытия. Сборщик продолжит работу автоматически.

> Перед запуском убедитесь, что все окна Chrome с профилем `CHROME_PROFILE_PATH` закрыты — иначе профиль будет заблокирован.

---

## Запуск

```bash
./start.sh
```

Скрипт последовательно:
1. Применяет миграции БД
2. Запускает сборщик в фоне (`manage.py collect`)
3. Запускает веб-сервер (`manage.py runserver 0.0.0.0:8000`)

Остановка — **Ctrl+C**, оба процесса завершатся корректно.

### Повторный запуск

Сборщик продолжает с сохранённого курсора. Прогресс хранится в `ParserState` внутри `db.sqlite3`.

---

## API

Базовый URL: `http://localhost:8000`

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/api/members/` | Список участников с фильтрацией и пагинацией |
| `GET` | `/api/members/{facebook_id}/` | Данные одного участника |
| `GET` | `/api/members/status/` | Количество участников по статусу обогащения |
| `GET` | `/api/docs/` | Swagger UI |
| `GET` | `/api/schema/` | OpenAPI схема (JSON/YAML) |

### Фильтры `/api/members/`

| Параметр | Тип | Значения | Описание |
|---|---|---|---|
| `gender` | string | `MALE`, `FEMALE` | Фильтр по полу |
| `enrichment` | string | `all`, `enriched`, `pending` | Фильтр по статусу обогащения |
| `limit` | integer | — | Размер страницы (по умолчанию 20) |
| `offset` | integer | — | Смещение для пагинации |

### Пример запроса

```bash
curl "http://localhost:8000/api/members/?gender=FEMALE&enrichment=enriched&limit=50&offset=0"
```

---

## Структура проекта

```
v3/
├── session.py                    # Захват сессии через Chrome (запускается автоматически)
├── start.sh                      # Точка входа
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py
│   └── urls.py
├── members/
│   ├── models.py                 # FacebookUser, FacebookSession, ParserState
│   ├── filters.py                # MemberFilter (django-filter)
│   ├── views.py                  # REST API
│   ├── serializers.py
│   └── management/commands/
│       └── collect.py            # Основной цикл сбора и обогащения
└── scraper/
    ├── graphql_client.py         # Пагинация участников через GraphQL
    ├── hovercard_client.py       # Обогащение профилей
    ├── group_scraper.py          # Парсинг GraphQL-ответов
    └── http_client.py            # Базовый HTTP-клиент
```
