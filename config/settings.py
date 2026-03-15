from pathlib import Path
from decouple import config, Csv
import os
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())


INSTALLED_APPS = [
    'jazzmin',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Libs
    'rest_framework',
    'corsheaders',
    'rest_framework.authtoken',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',

    # Custom
    'apps.users',
    'apps.orders',
    'apps.notifications',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'MAX_PAGE_SIZE': 100,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Allauth
SITE_ID = 1
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default='497803684602-gp0fhcgnoc3p4l7l3oju9vijhgrpethb.apps.googleusercontent.com'),
            'secret': config('GOOGLE_SECRET', default=''),
            'key': ''
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# Google OAuth
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='497803684602-gp0fhcgnoc3p4l7l3oju9vijhgrpethb.apps.googleusercontent.com')

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME'),
#         'USER': config('DB_USER'),
#         'PASSWORD': config('DB_PASSWORD'),
#         'HOST': config('DB_HOST'),
#         'PORT': config('DB_PORT'),
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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
TIME_ZONE = 'Asia/Bishkek'

USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Media
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# User
AUTH_USER_MODEL = 'users.User'

# Allauth
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# Rest Auth
REST_AUTH = {
    'USE_JWT': True,
    'JWT_AUTH_COOKIE': 'jwt-auth',
    'JWT_AUTH_REFRESH_COOKIE': 'jwt-refresh-token',
    'REGISTER_SERIALIZER': 'apps.users.serializers.CustomRegisterSerializer',
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Email backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = 'KargoPay <noreply@kargopay.app>'

# Swagger
SPECTACULAR_SETTINGS = {
    'TITLE': 'KargoPay API',
    'DESCRIPTION': 'Сервис пополнения AliPay',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    
    # Настройки авторизации
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [
        {
            'jwtAuth': []
        }
    ],
    'COMPONENT_SECURITY_SCHEMES': {
        'jwtAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
    },
    
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
    },
    
    # Теги для группировки endpoints
    'TAGS': [
        {'name': 'Auth', 'description': 'Авторизация и регистрация'},
        {'name': 'User', 'description': 'Профиль и реферальная система'},
        {'name': 'Orders', 'description': 'Заявки на пополнение'},
    ],

    'ENUM_NAME_OVERRIDES': {
        'OrderStatusEnum': 'apps.orders.models.Order.STATUS_CHOICES',
        'NotificationTypeEnum': 'apps.notifications.models.Notification.TYPE_CHOICES',
        'CurrencyFromEnum': 'apps.orders.models.ExchangeRate.CURRENCY_CHOICES',
        'CurrencyToEnum': 'apps.orders.models.ExchangeRate.CURRENCY_CHOICES',
    },
    
    'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': False,
}

# Jazzmin Admin Settings
JAZZMIN_SETTINGS = {
    "title": "KargoPay Admin",
    "title_logo": "logo.png",
    "site_brand": "KargoPay Admin",
    "welcome_sign": "Добро пожаловать в KargoPay Admin",
    "copyright": "KargoPay Ltd",
    "search_model": [
        "users.User",
        "orders.Order",
    ],
    "user_avatar": None,
    
    # Топ меню (только нужное)
    "topmenu_links": [
        {"name": "Главная", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Заявки", "url": "admin:orders_order_changelist"},
    ],
    
    # Боковое меню
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [
        "auth",
        "authtoken",
        "sites",
        "allauth",
        "account",
        "socialaccount",
    ],
    "hide_models": [],
    
    # Порядок разделов
    "order_with_respect_to": [
        "orders",
        "users",
        "notifications",
    ],
    
    # Иконки для моделей
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "users.User": "fas fa-user",
        "orders.Order": "fas fa-box",
        "orders.Service": "fas fa-concierge-bell",
        "orders.Bank": "fas fa-university",
        "orders.PaymentDetail": "fas fa-credit-card",
        "orders.ExchangeRate": "fas fa-exchange-alt",
        "notifications.Notification": "fas fa-bell",
        "notifications.PushToken": "fas fa-mobile-alt",
    },
    
    # Настройки отображения
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-indigo",
    "accent": "accent-indigo",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-indigo",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# Firebase Configuration
import os
from pathlib import Path

FIREBASE_CREDENTIALS = Path(BASE_DIR / 'firebase-key.json')
FIREBASE_PROJECT_ID = config('FIREBASE_PROJECT_ID', default='kargopay-app')

# ==========================================
# CORS Configuration
# ==========================================

# Разрешённые источники (фронтенд)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",      # React/Vue стандарт
    "http://127.0.0.1:3000",
    "http://localhost:5173",      # Vite
    "http://127.0.0.1:5173",
    "http://localhost:8080",      # Другой популярный порт
    "https://kargopay.app",       # Твой продакшен домен
    "https://www.kargopay.app",
]

# Если нужно разрешить ВСЕ (только для разработки!)
# CORS_ALLOW_ALL_ORIGINS = True

# Разрешить cookies и авторизационные заголовки
CORS_ALLOW_CREDENTIALS = True

# Разрешённые методы
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Разрешённые заголовки
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Preflight кэш (сколько браузер помнит ответ OPTIONS)
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 часа

# auth backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]