import os
from pathlib import Path
import ldap
from django_auth_ldap.config import LDAPSearch, GroupOfNamesType

# Possiamo tentare di caricare dotenv, ma se non è disponibile non è un problema
try:
    from dotenv import load_dotenv
    load_dotenv()  # Questo non genererà errori se il file .env non esiste
except ImportError:
    pass  # Python-dotenv non è installato o il file .env non esiste

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,web').split(',')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_yasg',
    'django_filters',
    # Local apps
    'reti_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'reti_project.urls'

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
                'reti_app.context_processors.app_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'reti_project.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': os.environ.get('DB_NAME', 'reti_db'),
        'USER': os.environ.get('DB_USER', 'reti_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'reti_password'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

# Lingua di default - configurabile tramite variabile d'ambiente
LANGUAGE_CODE = os.environ.get('DEFAULT_LANGUAGE', 'it')

# Lingue supportate
LANGUAGES = [
    ('it', 'Italiano'),
    ('en', 'English'),
]

# Directory per i file di traduzione
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

# Testo footer personalizzabile
FOOTER_TEXT = os.environ.get('FOOTER_TEXT', '')

TIME_ZONE = 'Europe/Rome'

USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
}

# CORS settings
CORS_ALLOWED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',')
CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',')

# Authentication settings
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# LDAP Authentication settings
# Configurazioni LDAP tramite variabili d'ambiente
AUTH_LDAP_SERVER_URI = os.environ.get('LDAP_SERVER_URI', '')

# Bind credentials (vuoti per bind anonimo)
AUTH_LDAP_BIND_DN = os.environ.get('LDAP_BIND_DN', '')
AUTH_LDAP_BIND_PASSWORD = os.environ.get('LDAP_BIND_PASSWORD', '')

# Base di ricerca e filtro degli utenti
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    os.environ.get('LDAP_USER_SEARCH_BASE', ''),
    ldap.SCOPE_SUBTREE, 
    os.environ.get('LDAP_USER_SEARCH_FILTER', 'mail=%(user)s')
)

# Mapping degli attributi LDAP agli attributi dell'utente Django
AUTH_LDAP_USER_ATTR_MAP = {
    "first_name": os.environ.get('LDAP_ATTR_FIRST_NAME', 'givenName'),
    "last_name": os.environ.get('LDAP_ATTR_LAST_NAME', 'sn'),
    "email": os.environ.get('LDAP_ATTR_EMAIL', 'mail'),
}

# Domain suffix to append if the username doesn't contain it
AUTH_LDAP_USER_SUFFIX = os.environ.get('LDAP_USER_SUFFIX', '')

# Configurazione per il login
AUTHENTICATION_BACKENDS = [
    'reti_app.auth.RootOrLDAPBackend',  # Backend personalizzato che gestisce caso speciale per root
    'django.contrib.auth.backends.ModelBackend',
]

# Logging dettagliato per il debug dell'autenticazione LDAP
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django_auth_ldap': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
} 