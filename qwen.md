# KargoPay Backend

**Сервис пополнения AliPay** — Django REST API бэкенд для сервиса пополнения электронных кошельков (AliPay, WeChat) через банки Кыргызстана.

---

## 📋 Оглавление

- [Технологический стек](#технологический-стек)
- [Структура проекта](#структура-проекта)
- [Приложения](#приложения)
- [Модели данных](#модели-данных)
- [API Endpoints](#api-endpoints)
- [Аутентификация](#аутентификация)
- [Безопасность](#безопасность)
- [Конвенции разработки](#конвенции-разработки)
- [Команды для разработки](#команды-для-разработки)
- [Переменные окружения](#переменные-окружения)

---

## Технологический стек

| Категория | Технология |
|-----------|------------|
| **Фреймворк** | Django 6.0.3 |
| **API** | Django REST Framework 3.16.1 |
| **Аутентификация** | djangorestframework-simplejwt 5.5.1 |
| **База данных** | PostgreSQL / SQLite3 |
| **OAuth** | django-allauth 65.14.3 (Google) |
| **Админка** | django-jazzmin 3.0.3 |
| **Документация** | drf-spectacular 0.29.0 (OpenAPI 3.0) |
| **Push-уведомления** | Firebase Admin SDK 7.2.0 |
| **CORS** | django-cors-headers 4.9.0 |
| **Environment** | python-decouple 3.8 |

---

## Структура проекта

```
kargopay-backend/
├── config/                 # Основной конфиг Django
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py         # Настройки проекта
│   ├── urls.py             # Корневой URLconf
│   ├── wsgi.py
│   └── firebase.py         # Firebase конфигурация
│
├── apps/                   # Пользовательские приложения
│   ├── __init__.py
│   ├── users/              # Пользователи и аутентификация
│   │   ├── models.py       # CustomUser, EmailVerificationCode
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── orders/             # Заявки на пополнение
│   │   ├── models.py       # Order, Service, Bank, ExchangeRate
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   └── notifications/      # Уведомления
│       ├── models.py       # Notification, PushToken
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── admin.py
│
├── media/                  # Загружаемые файлы
│   ├── receipts/           # Чеки об оплате
│   ├── services/           # Иконки услуг
│   ├── banks/              # Логотипы банков
│   └── payment/qr/         # QR-коды
│
├── manage.py               # Django CLI утилита
├── requirements.txt        # Зависимости Python
├── schema.yaml             # OpenAPI спецификация
├── db.sqlite3              # База данных (dev)
└── .env                    # Переменные окружения (не в git)
```

---

## Приложения

### `apps.users`
- Кастомная модель пользователя с email вместо username
- Реферальная система (реферальные коды, бонусы)
- Система скидок (Bronze: 0.5%, Silver: 1.0%, Gold: 2.0%)
- Коды подтверждения email
- Google OAuth интеграция

### `apps.orders`
- Заявки на пополнение (Order)
- Услуги (Service): AliPay, WeChat и др.
- Банки (Bank): mBank, Optima и др.
- Курсы валют (ExchangeRate)
- Платёжные реквизиты (PaymentDetail)

### `apps.notifications`
- Уведомления пользователей (Notification)
- Push-токены устройств (PushToken)
- Группировка уведомлений по датам
- Firebase push-рассылки

---

## Модели данных

### User (apps.users)
```python
email          # EmailField (уникальный, для аутентификации)
phone          # CharField (опционально)
pin_code       # CharField(4) (для быстрых операций)
referral_code  # CharField(10) (уникальный реферальный код)
referred_by    # ForeignKey (self) (пригласивший пользователь)
total_orders   # PositiveIntegerField (всего операций)
total_bonus    # DecimalField (накопленные бонусы)
first_order_discount_used  # BooleanField
alipay_qr_code # ImageField (QR-код AliPay пользователя, опционально)
```

### EmailVerificationCode (apps.users)
```python
user       # ForeignKey(User)
code       # CharField(6)
is_used    # BooleanField
expires_at # DateTimeField
```

### Order (apps.orders)
```python
user              # ForeignKey(User)
service           # ForeignKey(Service)
bank              # ForeignKey(Bank)
amount_from       # DecimalField (сумма к оплате)
currency_from     # CharField (KGS/RUB/USD)
amount_to         # DecimalField (сумма зачисления)
currency_to       # CharField (CNY/USD)
exchange_rate     # DecimalField
recipient_account # CharField (опционально, кошелёк/телефон)
receipt_image     # ImageField (чек об оплате)
recipient_qr_code # ImageField (QR получателя)
status            # CharField (PENDING/COMPLETED/REJECTED)
manager_comment   # TextField
discount_percent  # DecimalField
discount_amount   # DecimalField
final_amount      # DecimalField
```

### Service, Bank, PaymentDetail, ExchangeRate (apps.orders)
```python
# Service
name         # CharField
slug         # SlugField (уникальный)
description  # TextField
is_active    # BooleanField
icon         # ImageField

# Bank
name      # CharField
slug      # SlugField (уникальный)
logo      # ImageField
is_active # BooleanField

# PaymentDetail
service         # ForeignKey(Service)
bank            # ForeignKey(Bank)
account_number  # CharField
qr_code         # ImageField
recipient_name  # CharField
additional_info # TextField
is_active       # BooleanField

# ExchangeRate
from_currency # CharField (KGS/RUB/USD/CNY)
to_currency   # CharField (KGS/RUB/USD/CNY)
rate          # DecimalField
is_active     # BooleanField
```

### Notification (apps.notifications)
```python
user                # ForeignKey(User)
title               # CharField
message             # TextField
notification_type   # CharField (ORDER_CREATED, ORDER_COMPLETED, etc.)
related_object_id   # PositiveIntegerField
related_object_type # CharField
is_read             # BooleanField
is_sent             # BooleanField (push отправлен)
```

### PushToken (apps.notifications)
```python
user         # ForeignKey(User)
token        # CharField(500) (уникальный)
device_type  # CharField (web/ios/android)
device_info  # CharField
is_active    # BooleanField
last_used_at # DateTimeField
```

---

## API Endpoints

### Auth (Авторизация и регистрация)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/auth/login/` | Вход по email/password |
| POST | `/api/v1/auth/logout/` | Выход |
| POST | `/api/v1/auth/register/` | Регистрация |
| POST | `/api/v1/auth/password/reset/` | Сброс пароля |
| POST | `/api/v1/auth/password/reset/confirm/` | Подтверждение сброса |
| GET | `/api/v1/auth/google/` | Google OAuth |
| POST | `/api/v1/auth/verify-email/` | Подтверждение email |
| POST | `/api/v1/auth/resend-verification/` | Повторная отправка кода |

### User (Профиль)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/user/profile/` | Профиль пользователя |
| PUT | `/api/v1/user/profile/update/` | Обновление профиля (включая загрузку AliPay QR) |
| GET | `/api/v1/user/referral-info/` | Реферальная информация |
| POST | `/api/v1/user/push-token/` | Сохранение push-токена |

### Orders (Заявки)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/orders/services/` | Список услуг |
| GET | `/api/v1/orders/banks/` | Список банков |
| GET | `/api/v1/orders/rates/` | Курсы валют |
| GET | `/api/v1/orders/payment-details/` | Реквизиты (service+bank) |
| POST | `/api/v1/orders/orders/` | Создать заявку |
| GET | `/api/v1/orders/orders/{id}/` | Детали заявки |
| GET | `/api/v1/orders/orders/history/` | История заявок (с группировкой) |

### Notifications (Уведомления)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/notifications/` | Список уведомлений (с группировкой) |
| POST | `/api/v1/notifications/{id}/read/` | Отметить как прочитанное |
| POST | `/api/v1/notifications/mark-all-read/` | Прочитать все |
| GET | `/api/v1/notifications/unread-count/` | Количество непрочитанных |

### Документация
| Endpoint | Описание |
|----------|----------|
| `/api/v1/docs/` | Swagger UI |
| `/api/v1/redoc/` | ReDoc |
| `/api/v1/schema/` | OpenAPI JSON |

---

## Аутентификация

### JWT Token
- **Access token**: 60 минут
- **Refresh token**: 1 день (с ротацией и blacklist)
- **Header**: `Authorization: Bearer <token>`

### Google OAuth
```python
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID'),
            'secret': config('GOOGLE_SECRET'),
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}
```

### Custom User Model
- `AUTH_USER_MODEL = 'apps.users.User'`
- Аутентификация по email (не по username)
- `ACCOUNT_AUTHENTICATION_METHOD = 'email'`
- `ACCOUNT_EMAIL_REQUIRED = True`

---

## Безопасность

### CORS Configuration
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
CORS_ALLOW_CREDENTIALS = True
```

### Password Validators
- UserAttributeSimilarityValidator
- MinimumLengthValidator
- CommonPasswordValidator
- NumericPasswordValidator

### Environment Variables
Все секреты вынесены в `.env`:
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET`
- `FIREBASE_PROJECT_ID`

---

## Конвенции разработки

### Код
- **Импорты**: стандартные → сторонние → локальные (с пустой строкой между группами)
- **Модели**: сначала константы (CHOICES), затем поля, потом методы
- **Методы моделей**: docstring с описанием и возвратом
- **Перевод**: все verbose_name оборачивать в `gettext_lazy as _`

### Модели
```python
class Meta:
    verbose_name = _('Название')
    verbose_name_plural = _('Названия')
    ordering = ['-created_at']
    indexes = [...]  # если нужны индексы

def __str__(self):
    return self.name  # или email, title и т.д.
```

### API Views
- Использовать `@action` decorator для custom endpoints
- Группировка endpoints через `@action(detail=False)` или `@action(detail=True)`
- Пагинация: `PageNumberPagination`, `page_size=10`, `max_page_size=100`

### Сериализаторы
- Явное указание `read_only_fields`
- `validate_<field>()` методы для валидации полей
- `create()` и `update()` с явными исключениями для readOnly

### Миграции
- Всегда запускать `python manage.py makemigrations` после изменений моделей
- Проверять миграции перед коммитом
- Не редактировать созданные миграции вручную

### Админка (Jazzmin)
```python
JAZZMIN_SETTINGS = {
    "title": "KargoPay Admin",
    "site_brand": "KargoPay Admin",
    "icons": {...},
    "order_with_respect_to": ["orders", "users", "notifications"],
}
```

### Локализация
- `LANGUAGE_CODE = 'ru-ru'`
- `TIME_ZONE = 'Asia/Bishkek'`
- Все строки в моделях через `_('строка')`

---

## Команды для разработки

```bash
# Запуск сервера
python manage.py runserver

# Миграции
python manage.py makemigrations
python manage.py migrate

# Создать суперпользователя
python manage.py createsuperuser

# Сбор статиков
python manage.py collectstatic

# Тесты
python manage.py test

# Проверка типов (если используется mypy)
mypy .

# Форматирование (если используется black/ruff)
black .
ruff check .
```

---

## Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
DB_NAME=kargopay
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# Email
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_SECRET=your-client-secret

# Firebase
FIREBASE_PROJECT_ID=kargopay-app
```

---

## Реферальная система

### Уровни скидок
| Уровень | Операций | Скидка |
|---------|----------|--------|
| Bronze | 0-4 | 0.0005% |
| Silver | 5-9 | 0.001% |
| Gold | 10+ | 0.002% |

### Первая операция
- Новые пользователи по реферальной ссылке получают 0.005% скидку на первую операцию
- Скидка суммируется с уровнем (выбирается максимальная)

---

## Уведомления

### Типы уведомлений
- `ORDER_CREATED` — Заявка создана
- `ORDER_COMPLETED` — Заявка выполнена
- `ORDER_REJECTED` — Заявка отклонена
- `BONUS_RECEIVED` — Бонус получен
- `PROMO` — Акция
- `SYSTEM` — Системное

### Группировка
Уведомления группируются по датам:
- **Сегодня**
- **Вчера**
- **N дн. назад** (последние 7 дней)
- **ДД.ММ.ГГГГ** (более старые)

---

## Firebase Push Notifications

```python
FIREBASE_CREDENTIALS = Path(BASE_DIR / 'firebase-key.json')
FIREBASE_PROJECT_ID = config('FIREBASE_PROJECT_ID', default='kargopay-app')
```

Push-токены сохраняются в модели `PushToken` и используются для отправки уведомлений через Firebase Admin SDK.

---

## License

© 2026 KargoPay Ltd
