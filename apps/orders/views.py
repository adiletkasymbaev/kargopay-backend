from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db.models import Q
from .models import Service, Bank, PaymentDetail, ExchangeRate, Order
from .serializers import (
    ServiceSerializer, BankSerializer, PaymentDetailSerializer,
    PaymentDetailCreateSerializer, ExchangeRateSerializer,
    ExchangeRateCreateSerializer, OrderCreateSerializer,
    OrderSerializer, OrderStatusUpdateSerializer
)
from .pagination import DateGroupedPagination


# === Публичные endpoints (без авторизации) ===

@extend_schema(tags=['Orders'], summary='Список услуг')
class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(tags=['Orders'], summary='Список банков')
class BankListView(generics.ListAPIView):
    queryset = Bank.objects.filter(is_active=True)
    serializer_class = BankSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(tags=['Orders'], summary='Курсы валют')
class ExchangeRateListView(generics.ListAPIView):
    queryset = ExchangeRate.objects.filter(is_active=True).order_by('-updated_at')
    serializer_class = ExchangeRateSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(
    tags=['Orders'],
    summary='Реквизиты для оплаты',
    description='Получить реквизиты для конкретной пары услуга+банк',
    parameters=[
        OpenApiParameter('service', int, description='ID услуги'),
        OpenApiParameter('bank', int, description='ID банка'),
    ],
)
class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class = PaymentDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        service_id = self.request.query_params.get('service')
        bank_id = self.request.query_params.get('bank')

        payment_detail = PaymentDetail.objects.filter(
            service_id=service_id,
            bank_id=bank_id,
            is_active=True
        ).first()

        if not payment_detail:
            from rest_framework.exceptions import NotFound
            raise NotFound("Реквизиты не найдены для данной пары услуга+банк")

        return payment_detail


# === Авторизированные endpoints ===

@extend_schema(
    tags=['Orders'],
    summary='Создать заявку',
    description='''Создание новой заявки на пополнение с загрузкой чека.

**Тело запроса:**
- `service` (integer) — ID услуги
- `bank` (integer) — ID банка
- `amount_from` (number) — сумма к оплате
- `currency_from` (string) — валюта оплаты (KGS, RUB, USD)
- `currency_to` (string) — валюта зачисления (CNY, USD)
- `recipient_account` (string) — счёт получателя (телефон или номер кошелька)
- `recipient_qr_code` (string, опционально) — QR код получателя в формате base64 (data:image/png;base64,...)
- `receipt_image` (string) — чек об оплате в формате base64 (data:image/png;base64,...)

**Важно:** Изображения должны передаваться в формате base64 с data URI префиксом.
Пример: `"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."`

**Возвращаемые данные:**
- `id` — ID созданной заявки
- `service` — ID услуги
- `bank` — ID банка
- `amount_from` — сумма к оплате
- `currency_from` — валюта оплаты
- `currency_to` — валюта зачисления
- `amount_to` — сумма зачисления (рассчитывается автоматически)
- `exchange_rate` — применённый курс
- `discount_percent` — процент скидки
- `discount_amount` — сумма скидки
- `final_amount` — итоговая сумма
- `recipient_account` — счёт получателя
- `status` — статус заявки (PENDING)
- `created_at` — дата создания''',
    request=OrderCreateSerializer,
    responses={
        201: OrderCreateSerializer,
        400: {'description': 'Ошибка валидации данных'},
        401: {'description': 'Пользователь не авторизован'},
    },
    examples=[
        OpenApiExample(
            'Создание заявки',
            value={
                'service': 1,
                'bank': 1,
                'amount_from': '5000',
                'currency_from': 'KGS',
                'currency_to': 'CNY',
                'recipient_account': '+996 700 123 456',
                'recipient_qr_code': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...',
                'receipt_image': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...'
            },
            request_only=True
        ),
        OpenApiExample(
            'Успешный ответ',
            value={
                'id': 1,
                'service': 1,
                'bank': 1,
                'amount_from': '5000.00',
                'currency_from': 'KGS',
                'currency_to': 'CNY',
                'amount_to': '597.00',
                'exchange_rate': '0.1200',
                'discount_percent': '0.50',
                'discount_amount': '2.99',
                'final_amount': '5000.00',
                'recipient_account': '+996 700 123 456',
                'status': 'PENDING',
                'created_at': '2026-03-15T12:00:00Z'
            },
            status_codes=[201]
        ),
        OpenApiExample(
            'Ошибка валидации',
            value={
                'receipt_image': ['Изображение чека обязательно'],
                'amount_from': ['Сумма должна быть положительной']
            },
            status_codes=[400]
        )
    ],
)
class OrderCreateView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save()


@extend_schema(
    tags=['Orders'],
    summary='История заявок',
    description='''Получить все заявки текущего пользователя с группировкой по датам.

Заявки возвращаются в хронологическом порядке (новые первыми) и группируются по датам:
- **Сегодня** — заявки за текущий день
- **Вчера** — заявки за вчерашний день
- **N дн. назад** — заявки за последние 7 дней
- **ДД.ММ.ГГГГ** — более старые заявки

**Параметры запроса:**
- `page` (integer) — номер страницы (по умолчанию 1)
- `page_size` (integer) — количество элементов на странице (по умолчанию 10, максимум 100)
- `status` (string, опционально) — фильтр по статусу заявки:
  - `PENDING` — На проверке
  - `COMPLETED` — Выполнено
  - `REJECTED` — Отклонено
  - если не указан, возвращаются все заявки

**Возвращаемые данные:**
- `count` — общее количество заявок
- `next` — URL следующей страницы (или null)
- `previous` — URL предыдущей страницы (или null)
- `total_pages` — общее количество страниц
- `current_page` — текущая страница
- `groups` — массив групп заявок по датам
  - `date` — название группы (например, "Сегодня", "Вчера", "15.03.2026")
  - `items` — массив заявок в этой группе

**Структура заявки:**
- `id` — идентификатор заявки
- `user` — ID пользователя
- `user_email` — email пользователя
- `service` — ID услуги
- `service_name` — название услуги
- `bank` — ID банка
- `bank_name` — название банка
- `amount_from` — сумма к оплате
- `currency_from` — валюта оплаты
- `amount_to` — сумма зачисления
- `currency_to` — валюта зачисления
- `exchange_rate` — применённый курс
- `recipient_account` — счёт получателя
- `receipt_image` — URL чека об оплате
- `status` — статус (PENDING, COMPLETED, REJECTED)
- `manager_comment` — комментарий менеджера
- `discount_percent` — процент скидки
- `discount_amount` — сумма скидки
- `final_amount` — итоговая сумма
- `created_at` — дата создания
- `updated_at` — дата обновления
- `completed_at` — дата выполнения''',
    parameters=[
        OpenApiParameter(
            name='page',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Номер страницы',
            default=1,
            examples=[OpenApiExample('Страница 1', value=1)]
        ),
        OpenApiParameter(
            name='page_size',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Количество элементов на странице',
            default=10,
            examples=[OpenApiExample('10 элементов', value=10)]
        ),
        OpenApiParameter(
            name='status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Фильтр по статусу заявки',
            required=False,
            enum=['PENDING', 'COMPLETED', 'REJECTED'],
            examples=[
                OpenApiExample('На проверке', value='PENDING'),
                OpenApiExample('Выполнено', value='COMPLETED'),
                OpenApiExample('Отклонено', value='REJECTED'),
            ]
        ),
    ],
    responses={
        200: {
            'description': 'Список заявок с группировкой по датам',
            'content': {
                'application/json': {
                    'example': {
                        'count': 42,
                        'next': '/api/v1/orders/history/?page=2',
                        'previous': None,
                        'total_pages': 5,
                        'current_page': 1,
                        'groups': [
                            {
                                'date': 'Сегодня',
                                'items': [
                                    {
                                        'id': 1,
                                        'user_email': 'user@example.com',
                                        'service_name': 'AliPay',
                                        'bank_name': 'Optima',
                                        'amount_from': '1000.00',
                                        'currency_from': 'KGS',
                                        'amount_to': '119.40',
                                        'currency_to': 'CNY',
                                        'exchange_rate': '0.1200',
                                        'status': 'COMPLETED',
                                        'created_at': '2026-03-14T10:30:00Z'
                                    }
                                ]
                            },
                            {
                                'date': 'Вчера',
                                'items': [
                                    {
                                        'id': 2,
                                        'user_email': 'user@example.com',
                                        'service_name': 'WeChat',
                                        'bank_name': 'mBank',
                                        'amount_from': '500.00',
                                        'status': 'PENDING',
                                        'created_at': '2026-03-13T15:00:00Z'
                                    }
                                ]
                            },
                            {
                                'date': '10.03.2026',
                                'items': []
                            }
                        ]
                    }
                }
            }
        },
        401: {'description': 'Пользователь не авторизован'},
    },
)
class OrderHistoryView(generics.ListAPIView):
    serializer_class = OrderSerializer
    pagination_class = DateGroupedPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Order.objects.filter(user=self.request.user).order_by('-created_at')
        
        # Фильтр по статусу
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


@extend_schema(
    tags=['Orders'],
    summary='Детали заявки',
    description='Получить детали конкретной заявки',
)
class OrderDetailView(generics.RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)