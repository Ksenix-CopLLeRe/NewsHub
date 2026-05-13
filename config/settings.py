"""
Django settings for config project.
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

_secret_key = os.getenv('DJANGO_SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
if not _secret_key:
    if DEBUG:
        _secret_key = 'django-insecure-local-dev-only-not-for-production'
    else:
        raise RuntimeError('DJANGO_SECRET_KEY environment variable is not set')
SECRET_KEY = _secret_key

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    'django_prometheus',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'news',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

# Database
_database_url = os.getenv('DATABASE_URL')
if _database_url:
    DATABASES = {'default': dj_database_url.parse(_database_url, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ============ МИКРОСЕРВИСЫ ============

# URL микросервисов (используем имена сервисов из docker-compose)
# Внутри Docker сети:
# - feed-service доступен как feed-service:8000
# - reactions-service доступен как reactions-service:8000  
# - user-content-service доступен как user-content-service:8002
FEED_SERVICE_URL = os.getenv('FEED_SERVICE_URL', 'http://feed-service:8000')
REACTIONS_SERVICE_URL = os.getenv('REACTIONS_SERVICE_URL', 'http://reactions-service:8000')
USER_CONTENT_SERVICE_URL = os.getenv('USER_CONTENT_SERVICE_URL', 'http://user-content-service:8002')

# Для локальной разработки (вне Docker) можно переопределить:
# FEED_SERVICE_URL = os.getenv('FEED_SERVICE_URL', 'http://localhost:8003')
# REACTIONS_SERVICE_URL = os.getenv('REACTIONS_SERVICE_URL', 'http://localhost:8004')
# USER_CONTENT_SERVICE_URL = os.getenv('USER_CONTENT_SERVICE_URL', 'http://localhost:8002')

# Режим работы с микросервисами
USE_MICROSERVICES = os.getenv('USE_MICROSERVICES', 'true').lower() == 'true'

# Таймауты для запросов к микросервисам (секунды)
MICROSERVICE_TIMEOUT = float(os.getenv('MICROSERVICE_TIMEOUT', '3.0'))

# Для обратной совместимости (если нужно)
if not USE_MICROSERVICES:
    # Используем локальные модели вместо микросервисов
    pass

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============ Sentry ============
_sentry_dsn = os.getenv('SENTRY_DSN')
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.0')),
        environment=os.getenv('SENTRY_ENVIRONMENT', os.getenv('ENVIRONMENT', 'production')),
        send_default_pii=False,
    )