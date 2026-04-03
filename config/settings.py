"""
Django settings for config project.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-0s=j71^ih&+_=t2jkk!6+$55w1ud0br!0al7+*z(v%f7j7mw%8')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,news').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'news',
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

# Database - SQLite для Django (пользователи, сессии)
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