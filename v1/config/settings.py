from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='dev-secret-key-change-in-production')
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'members',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── База данных (PostgreSQL) ──────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     env('POSTGRES_DB',       default='fb_members'),
        'USER':     env('POSTGRES_USER',     default='postgres'),
        'PASSWORD': env('POSTGRES_PASSWORD', default='postgres'),
        'HOST':     env('POSTGRES_HOST',     default='postgres'),
        'PORT':     env('POSTGRES_PORT',     default='5432'),
    }
}

# ── Celery ───────────────────────────────────────────────────────────────────

CELERY_BROKER_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULE_FILENAME = '/tmp/celerybeat-schedule'
CELERY_TASK_ROUTES = {
    'members.capture_session': {'queue': 'capture'},
}

CELERY_BEAT_SCHEDULE = {
    'enrich-members-every-5-min': {
        'task': 'members.enrich_members',
        'schedule': 300,
    },
    'scrape-group-every-3-min': {
        'task': 'members.scrape_group',
        'schedule': 180,
    },
    'capture-session-daily': {
        'task': 'members.capture_session',
        'schedule': 86400,  # раз в сутки как страховка
    },
}

# ── Scraper ──────────────────────────────────────────────────────────────────

GROUP_URL            = env('GROUP_URL',         default='https://www.facebook.com/groups/CrimeaBeauty')
GROUP_ID             = env('GROUP_ID',          default='1883332381741292')
MEMBERS_DOC_ID       = env('MEMBERS_DOC_ID',    default='26296205566653090')
HOVERCARD_DOC_ID     = env('HOVERCARD_DOC_ID',  default='33705242655757750')
FACEBOOK_IP          = env('FACEBOOK_IP',       default='31.13.72.36')
SESSION_DATA_PATH     = env('SESSION_DATA_PATH',    default=str(BASE_DIR / 'session_data.json'))
SESSION_MAX_AGE_HOURS = env.int('SESSION_MAX_AGE_HOURS', default=12)
REQUEST_DELAY_MIN     = env.float('REQUEST_DELAY_MIN', default=1.0)
REQUEST_DELAY_MAX     = env.float('REQUEST_DELAY_MAX', default=2.0)
AVATARS_DIR           = env('AVATARS_DIR', default=str(BASE_DIR / 'media' / 'avatars'))

# ── Elasticsearch ─────────────────────────────────────────────────────────────

ES_URL   = env('ES_URL',   default='http://localhost:9200')
ES_INDEX = env('ES_INDEX', default='fb_members')

# ── DRF ──────────────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE':       'Facebook Group Members API',
    'DESCRIPTION': 'API для доступа к данным участников группы Facebook',
    'VERSION':     '1.0.0',
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'scraper':              {'handlers': ['console'], 'level': 'INFO',    'propagate': False},
        'members':              {'handlers': ['console'], 'level': 'INFO',    'propagate': False},
        'elastic_transport':    {'handlers': [],          'level': 'WARNING', 'propagate': False},
    },
}

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_TZ = True
