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
    'django_filters',
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

GROUP_URL             = env('GROUP_URL',             default='https://www.facebook.com/groups/CrimeaBeauty')
GROUP_ID              = env('GROUP_ID',              default='1883332381741292')
MEMBERS_DOC_ID        = env('MEMBERS_DOC_ID',        default='26296205566653090')
HOVERCARD_DOC_ID      = env('HOVERCARD_DOC_ID',      default='33705242655757750')
FACEBOOK_IP           = env('FACEBOOK_IP',           default='31.13.72.36')
SESSION_DATA_PATH     = env('SESSION_DATA_PATH',     default=str(BASE_DIR / 'session_data.json'))
REQUEST_DELAY_MIN     = env.float('REQUEST_DELAY_MIN', default=1.0)
REQUEST_DELAY_MAX     = env.float('REQUEST_DELAY_MAX', default=2.0)
BATCH_SIZE            = env.int('BATCH_SIZE',        default=10)
AVATARS_DIR           = env('AVATARS_DIR',           default=str(BASE_DIR / 'media' / 'avatars'))
ENRICH_ENABLED        = env.bool('ENRICH_ENABLED',   default=True)

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Facebook Group Members API',
    'VERSION': '1.0.0',
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
        'scraper': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'members': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_TZ = True
