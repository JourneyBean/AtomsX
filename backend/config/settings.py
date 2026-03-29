"""
Django settings for AtomsX Visual Coding Platform.

MVP Phase: OIDC Auth + Workspace Management + Agent Conversation + Preview
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# In DEBUG mode, load .env file (override Docker environment variables)
# This allows hot-reloading config changes during development.
# In production, use Docker/K8s environment variables directly.
_DEBUG_ENV_LOADED = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'
_ENV_FILE = BASE_DIR / '.env'
if _DEBUG_ENV_LOADED and _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

# ALLOWED_HOSTS: When running in Docker Compose, include the 'backend' service name
# for container-to-container communication. Default is for local development only.
# Example for Docker: DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend,gateway
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'corsheaders',
    'channels',  # WebSocket support

    # Local apps
    'apps.core',
    'apps.users',
    'apps.workspaces',
    'apps.sessions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
        'DIRS': [BASE_DIR / 'backend' / 'templates'],
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

# ASGI application for WebSocket support
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'atomsx'),
        'USER': os.environ.get('POSTGRES_USER', 'atomsx'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'atomsx_password'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

# Redis
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')

# Workspace domain configuration
# ATOMSX_PREVIEW_DOMAIN: Domain for workspace preview URLs (development/debugging)
# Format: {workspace-id}.{ATOMSX_PREVIEW_DOMAIN}
ATOMSX_PREVIEW_DOMAIN = os.environ.get('ATOMSX_PREVIEW_DOMAIN', 'preview.local')

# ATOMSX_DEPLOY_DOMAIN: Domain for workspace deployed app URLs (production)
# Format: {workspace-id}.{ATOMSX_DEPLOY_DOMAIN}
ATOMSX_DEPLOY_DOMAIN = os.environ.get('ATOMSX_DEPLOY_DOMAIN', 'apps.local')

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': f'redis://{REDIS_HOST}:{REDIS_PORT}/1',
    }
}

# Celery
CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Celery Beat schedule for periodic tasks
CELERY_BEAT_SCHEDULE = {
    'cleanup-orphaned-tokens': {
        'task': 'apps.workspaces.tasks.cleanup_orphaned_tokens',
        'schedule': 300.0,  # Run every 5 minutes
    },
}

# Channel layers for WebSocket support
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(REDIS_HOST, int(REDIS_PORT))],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'backend' / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User model
AUTH_USER_MODEL = 'users.User'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.core.authentication.CsrfExemptSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# CORS settings
# Note: User workspace domains (preview/deploy) are NOT trusted for CORS
# Only the AtomsX platform frontend is allowed
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173'
).split(',')

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins - must include the gateway and frontend ports
# Note: User workspace domains (preview/deploy) are NOT trusted for CSRF
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:18080,http://localhost:5173,'
    'http://127.0.0.1:18080,http://127.0.0.1:5173'
).split(',')

# OIDC Configuration (to be expanded in auth implementation)
OIDC_PROVIDER_URL = os.environ.get(
    'OIDC_PROVIDER_URL',
    'http://authentik-server:9000/application/o/atomsx/'
)
OIDC_CLIENT_ID = os.environ.get('OIDC_CLIENT_ID', 'atomsx')
OIDC_CLIENT_SECRET = os.environ.get('OIDC_CLIENT_SECRET', 'change-me')
OIDC_REDIRECT_URI = os.environ.get(
    'OIDC_REDIRECT_URI',
    'http://localhost:8000/api/auth/callback'
)

# Docker-in-Docker configuration
DIND_ENABLED = os.environ.get('DIND_ENABLED', 'true').lower() == 'true'
DIND_SOCKET_PATH = os.environ.get('DIND_SOCKET_PATH', '/var/run/dind/docker.sock')
DIND_HOST = os.environ.get('DIND_HOST', '')  # Optional TCP connection (e.g., 'tcp://dind:2375')

# Docker client connection - use dind socket by default when dind is enabled
if DIND_ENABLED:
    if DIND_HOST:
        DOCKER_HOST = DIND_HOST  # Use TCP connection if specified
    else:
        DOCKER_HOST = os.environ.get('DOCKER_HOST', f'unix://{DIND_SOCKET_PATH}')
else:
    # When dind is disabled, DOCKER_HOST must be explicitly set (reject operations)
    DOCKER_HOST = os.environ.get('DOCKER_HOST', '')

WORKSPACE_NETWORK_NAME = os.environ.get('WORKSPACE_NETWORK_NAME', 'atomsx-workspaces')
WORKSPACE_BASE_IMAGE = os.environ.get('WORKSPACE_BASE_IMAGE', 'atomsx-workspace:latest')

# Workspace creation timeout configuration (in seconds)
# Soft timeout: task receives SoftTimeLimitExceeded exception, allowing cleanup
# Hard timeout: task is forcibly terminated by Celery
WORKSPACE_CREATION_SOFT_TIMEOUT = int(os.environ.get('WORKSPACE_CREATION_SOFT_TIMEOUT', '300'))  # Default: 5 minutes
WORKSPACE_CREATION_HARD_TIMEOUT = int(os.environ.get('WORKSPACE_CREATION_HARD_TIMEOUT', '360'))  # Default: 6 minutes

# Workspace deletion timeout configuration (in seconds)
# If a workspace stays in 'deleting' status longer than this threshold,
# the delete API will re-trigger the deletion task (assuming previous task stuck)
WORKSPACE_DELETION_TIMEOUT = int(os.environ.get('WORKSPACE_DELETION_TIMEOUT', '300'))  # Default: 5 minutes

# Anthropic API configuration
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ANTHROPIC_BASE_URL = os.environ.get('ANTHROPIC_BASE_URL', '')
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', '')  # e.g., 'claude-opus-4-6', 'claude-sonnet-4-6'

# Workspace Client configuration
WORKSPACE_CLIENT_WS_URL = os.environ.get('WORKSPACE_CLIENT_WS_URL', 'ws://backend:8000')
WORKSPACE_CLIENT_HTTP_URL = os.environ.get('WORKSPACE_CLIENT_HTTP_URL', 'http://backend:8000')
INTERNAL_API_TOKEN = os.environ.get('ATOMSX_INTERNAL_API_TOKEN', 'dev-internal-token')

# Workspace data storage configuration
# WORKSPACE_DATA_ROOT: Path inside Celery worker container for creating directories
# HOST_WORKSPACE_DATA_ROOT: Actual host path for Docker bind mounts (dev mode)
WORKSPACE_DATA_ROOT = os.environ.get(
    'ATOMSX_WORKSPACE_DATA_ROOT',
    '/var/opt/atomsx/workspaces'
)
# In development with host Docker socket, use this for bind mount source path
# In production with dind, this should be same as WORKSPACE_DATA_ROOT
HOST_WORKSPACE_DATA_ROOT = os.environ.get(
    'ATOMSX_HOST_WORKSPACE_DATA_ROOT',
    WORKSPACE_DATA_ROOT  # Default: same as internal path (for dind mode)
)

# Django development server auto-reload configuration
# Watch .env file for changes so config updates trigger server reload
# (which re-runs dotenv loading above)
if DEBUG:
    STAT_RELOAD_FILES = [_ENV_FILE]