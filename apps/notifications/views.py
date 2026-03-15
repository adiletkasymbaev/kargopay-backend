from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db.models import Q
from django.utils import timezone
from .models import Notification, PushToken
from .serializers import (
    NotificationSerializer,
    PushTokenSerializer,
    PushTokenRegisterSerializer
)
from .pagination import NotificationGroupedPagination
from config.firebase import send_push_notification_multicast, initialize_firebase


@extend_schema_view(
    get=extend_schema(
        tags=['Notifications'],
        summary='Список уведомлений',
        description='''Получает все уведомления текущего пользователя с группировкой по датам.

Уведомления возвращаются в хронологическом порядке (новые первыми) и группируются по датам:
- **Сегодня** — уведомления за текущий день
- **Вчера** — уведомления за вчерашний день
- **N дн. назад** — уведомления за последние 7 дней
- **ДД.ММ.ГГГГ** — более старые уведомления

**Параметры запроса:**
- `page` (integer) — номер страницы (по умолчанию 1)
- `page_size` (integer) — количество элементов на странице (по умолчанию 10, максимум 100)

**Возвращаемые данные:**
- `count` — общее количество уведомлений
- `next` — URL следующей страницы (или null)
- `previous` — URL предыдущей страницы (или null)
- `total_pages` — общее количество страниц
- `current_page` — текущая страница
- `groups` — массив групп уведомлений по датам
  - `date` — название группы (например, "Сегодня", "Вчера", "15.03.2026")
  - `items` — массив уведомлений в этой группе

**Структура уведомления:**
- `id` — идентификатор уведомления
- `user` — ID пользователя
- `title` — заголовок уведомления
- `message` — текст уведомления
- `notification_type` — тип уведомления (WELCOME, ORDER_STATUS, PROMOTION и т.д.)
- `is_read` — статус прочтения
- `is_sent` — статус отправки push-уведомления
- `sent_at` — дата отправки push-уведомления
- `created_at` — дата создания
- `updated_at` — дата обновления
- `related_object_id` — ID связанного объекта (например, заказа)
- `related_object_type` — тип связанного объекта (например, "Order")''',
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
        ],
        responses={
            200: {
                'description': 'Список уведомлений с группировкой по датам',
                'content': {
                    'application/json': {
                        'example': {
                            'count': 25,
                            'next': '/api/v1/notifications/?page=2',
                            'previous': None,
                            'total_pages': 3,
                            'current_page': 1,
                            'groups': [
                                {
                                    'date': 'Сегодня',
                                    'items': [
                                        {
                                            'id': 5,
                                            'title': '✅ Заявка выполнена',
                                            'message': 'Ваша заявка #123 выполнена. Средства зачислены на AliPay.',
                                            'notification_type': 'ORDER_COMPLETED',
                                            'is_read': False,
                                            'created_at': '2026-03-14T10:30:00Z'
                                        },
                                        {
                                            'id': 4,
                                            'title': '🎉 Добро пожаловать!',
                                            'message': 'Спасибо за регистрацию в KargoPay',
                                            'notification_type': 'WELCOME',
                                            'is_read': True,
                                            'created_at': '2026-03-14T09:00:00Z'
                                        }
                                    ]
                                },
                                {
                                    'date': 'Вчера',
                                    'items': [
                                        {
                                            'id': 3,
                                            'title': '📍 Заказ создан',
                                            'message': 'Ваша заявка #122 принята в обработку',
                                            'notification_type': 'ORDER_CREATED',
                                            'is_read': True,
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
        examples=[
            OpenApiExample(
                'Запрос с пагинацией',
                value={'page': 2, 'page_size': 20},
                request_only=True
            ),
            OpenApiExample(
                'Ответ с группировкой по датам',
                value={
                    'count': 45,
                    'next': '/api/v1/notifications/?page=3&page_size=20',
                    'previous': '/api/v1/notifications/?page=1&page_size=20',
                    'total_pages': 3,
                    'current_page': 2,
                    'groups': [
                        {
                            'date': 'Сегодня',
                            'items': [
                                {
                                    'id': 25,
                                    'user': 1,
                                    'title': '🎉 Добро пожаловать!',
                                    'message': 'Спасибо за регистрацию в KargoPay',
                                    'notification_type': 'WELCOME',
                                    'is_read': True,
                                    'is_sent': True,
                                    'sent_at': '2026-03-14T10:00:00Z',
                                    'created_at': '2026-03-14T10:00:00Z',
                                    'updated_at': '2026-03-14T10:00:00Z',
                                    'related_object_id': None,
                                    'related_object_type': None
                                }
                            ]
                        },
                        {
                            'date': 'Вчера',
                            'items': []
                        }
                    ]
                },
                status_codes=[200]
            ),
            OpenApiExample(
                'Пустой список',
                value={
                    'count': 0,
                    'next': None,
                    'previous': None,
                    'total_pages': 0,
                    'current_page': 1,
                    'groups': []
                },
                status_codes=[200]
            )
        ],
    )
)
class NotificationListView(generics.ListAPIView):
    """Получить все уведомления пользователя с группировкой по датам"""
    serializer_class = NotificationSerializer
    pagination_class = NotificationGroupedPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).select_related('user').order_by('-created_at')


@extend_schema_view(
    get=extend_schema(
        tags=['Notifications'],
        summary='Количество непрочитанных уведомлений',
        description='''Возвращает количество непрочитанных уведомлений пользователя.
        
Полезно для отображения бейджа на иконке уведомлений в приложении.

**Возвращаемые данные:**
- `unread_count` — количество непрочитанных уведомлений''',
        responses={
            200: {'type': 'object', 'properties': {'unread_count': {'type': 'integer'}}},
            401: {'description': 'Пользователь не авторизован'},
        },
        examples=[
            OpenApiExample(
                'Успешный ответ',
                value={'unread_count': 5},
                status_codes=[200]
            )
        ],
    )
)
class UnreadNotificationCountView(APIView):
    """Получить количество непрочитанных уведомлений"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        return Response({'unread_count': count})


@extend_schema_view(
    post=extend_schema(
        tags=['Notifications'],
        summary='Отметить уведомление как прочитанное',
        description='''Отмечает конкретное уведомление как прочитанное.
        
Изменяет статус уведомления с "непрочитанное" на "прочитанное".

**Параметры:**
- `notification_id` (path) — идентификатор уведомления

**Возвращаемые данные:**
- `status` — статус операции ('success' или 'error')''',
        parameters=[
            OpenApiParameter(
                name='notification_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Идентификатор уведомления',
                required=True,
                examples=[OpenApiExample('ID уведомления', value=123)]
            ),
        ],
        responses={
            200: {'description': 'Уведомление отмечено как прочитанное', 'content': {'application/json': {'example': {'status': 'success'}}}},
            401: {'description': 'Пользователь не авторизован'},
            404: {'description': 'Уведомление не найдено'},
        },
        examples=[
            OpenApiExample(
                'Успешный ответ',
                value={'status': 'success'},
                status_codes=[200]
            ),
            OpenApiExample(
                'Уведомление не найдено',
                value={'error': 'Уведомление не найдено'},
                status_codes=[404]
            )
        ],
    )
)
class NotificationMarkAsReadView(APIView):
    """Отметить уведомление как прочитанное"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None

    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.is_read = True
            notification.save()
            return Response({'status': 'success'})
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Уведомление не найдено'},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema_view(
    post=extend_schema(
        tags=['Notifications'],
        summary='Отметить все уведомления как прочитанные',
        description='''Массово отмечает все непрочитанные уведомления пользователя как прочитанные.
        
Полезно при выходе из раздела уведомлений или при нажатии кнопки "Прочитать все".

**Возвращаемые данные:**
- `status` — статус операции ('success')''',
        responses={
            200: {'description': 'Все уведомления отмечены как прочитанные', 'content': {'application/json': {'example': {'status': 'success'}}}},
            401: {'description': 'Пользователь не авторизован'},
        },
        examples=[
            OpenApiExample(
                'Успешный ответ',
                value={'status': 'success'},
                status_codes=[200]
            )
        ],
    )
)
class NotificationMarkAllAsReadView(APIView):
    """Отметить все уведомления как прочитанные"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None

    def post(self, request):
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({'status': 'success'})


@extend_schema_view(
    post=extend_schema(
        tags=['Notifications'],
        summary='Зарегистрировать Push-токен',
        description='''Регистрирует или обновляет push-токен устройства для получения уведомлений.

Токен сохраняется в базе данных и связывается с текущим пользователем.
При повторной отправке того же токена данные обновляются.

**Тело запроса:**
- `token` (string) — уникальный токен устройства (FCM/APNS)
- `device_type` (string) — тип устройства: 'ios', 'android' или 'web'
- `device_info` (string, опционально) — название устройства или браузера (например, 'iPhone 15 Pro', 'Chrome 120')

**Возвращаемые данные:**
- `id` — идентификатор записи
- `token` — токен устройства
- `device_type` — тип устройства
- `device_info` — информация об устройстве
- `user` — ID пользователя
- `created_at` — дата регистрации''',
        request=PushTokenRegisterSerializer,
        responses={
            200: PushTokenSerializer,
            400: {'description': 'Ошибка валидации данных'},
            401: {'description': 'Пользователь не авторизован'},
        },
        examples=[
            OpenApiExample(
                'Запрос (Android)',
                value={
                    'token': 'fcm_device_token_12345',
                    'device_type': 'android',
                    'device_info': 'Samsung Galaxy S24'
                },
                request_only=True
            ),
            OpenApiExample(
                'Запрос (iOS)',
                value={
                    'token': 'apns_device_token_67890',
                    'device_type': 'ios',
                    'device_info': 'iPhone 15 Pro'
                },
                request_only=True
            ),
            OpenApiExample(
                'Запрос (Web)',
                value={
                    'token': 'fcm_web_token_abcde',
                    'device_type': 'web',
                    'device_info': 'Chrome 120 on Windows 11'
                },
                request_only=True
            ),
            OpenApiExample(
                'Успешный ответ',
                value={
                    'id': 1,
                    'token': 'fcm_device_token_12345',
                    'device_type': 'android',
                    'device_info': 'Samsung Galaxy S24',
                    'user': 42,
                    'created_at': '2026-03-14T10:30:00Z'
                },
                status_codes=[200]
            ),
            OpenApiExample(
                'Ошибка валидации',
                value={
                    'token': ['Это поле обязательно.'],
                    'device_type': ['Выберите допустимое значение: ios, android, web']
                },
                status_codes=[400]
            )
        ],
    )
)
class PushTokenRegisterView(APIView):
    """Регистрация push-токена устройства"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None

    def post(self, request):
        serializer = PushTokenRegisterSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            token = serializer.save()
            return Response(PushTokenSerializer(token).data)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema_view(
    post=extend_schema(
        tags=['Notifications'],
        summary='Удалить Push-токен',
        description='''Удаляет push-токен устройства.
        
Используется при выходе пользователя из приложения или при смене устройства.
После удаления push-уведомления больше не будут приходить на это устройство.

**Тело запроса:**
- `token` (string) — токен устройства для удаления

**Возвращаемые данные:**
- `status` — статус операции ('success')''',
        request={'type': 'object', 'properties': {'token': {'type': 'string'}}},
        responses={
            200: {'description': 'Токен успешно удалён', 'content': {'application/json': {'example': {'status': 'success'}}}},
            401: {'description': 'Пользователь не авторизован'},
        },
        examples=[
            OpenApiExample(
                'Запрос',
                value={'token': 'fcm_device_token_12345'},
                request_only=True
            ),
            OpenApiExample(
                'Успешный ответ',
                value={'status': 'success'},
                status_codes=[200]
            )
        ],
    )
)
class PushTokenDeleteView(APIView):
    """Удаление push-токена (например, при выходе)"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None

    def post(self, request):
        token = request.data.get('token')
        if token:
            PushToken.objects.filter(token=token, user=request.user).delete()
        return Response({'status': 'success'})


@extend_schema_view(
    post=extend_schema(
        tags=['Notifications'],
        summary='Отправить тестовое уведомление всем устройствам',
        description='''Отправляет тестовое push-уведомление на все активные устройства.

Используется для тестирования push-уведомлений в разработке.

**Тело запроса (опционально):**
- `title` (string) — заголовок уведомления (по умолчанию: "🔔 Тестовое уведомление")
- `message` (string) — текст уведомления (по умолчанию: "Если вы видите это уведомление, значит push работает!")

**Возвращаемые данные:**
- `status` — статус операции ('success')
- `sent_count` — количество отправленных уведомлений
- `devices` — список устройств, на которые были отправлены уведомления''',
        request={'type': 'object', 'properties': {'title': {'type': 'string'}, 'message': {'type': 'string'}}},
        responses={
            200: {'description': 'Тестовые уведомления отправлены', 'content': {'application/json': {'example': {'status': 'success', 'sent_count': 5, 'devices': ['android', 'ios', 'web']}}}},
            401: {'description': 'Пользователь не авторизован'},
            403: {'description': 'Доступ запрещён (только для персонала)'},
        },
        examples=[
            OpenApiExample(
                'Запрос с кастомным текстом',
                value={
                    'title': '🎉 Привет!',
                    'message': 'Это тестовое уведомление'
                },
                request_only=True
            ),
            OpenApiExample(
                'Успешный ответ',
                value={
                    'status': 'success',
                    'sent_count': 5,
                    'devices': ['android', 'ios', 'web']
                },
                status_codes=[200]
            ),
            OpenApiExample(
                'Нет активных устройств',
                value={
                    'status': 'success',
                    'sent_count': 0,
                    'devices': []
                },
                status_codes=[200]
            )
        ],
    )
)
class SendTestNotificationView(APIView):
    """Отправить тестовое уведомление на все устройства"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = None

    def post(self, request):
        title = request.data.get('title', '🔔 Тестовое уведомление')
        message = request.data.get('message', 'Если вы видите это уведомление, значит push работает!')
        
        # Инициализируем Firebase если нужно
        initialize_firebase()
        
        # Получаем все активные push-токены
        active_tokens = PushToken.objects.filter(is_active=True)
        
        if not active_tokens.exists():
            return Response({
                'status': 'success',
                'sent_count': 0,
                'devices': [],
                'message': 'Нет активных устройств для отправки уведомлений'
            })
        
        # Создаём тестовые уведомления для всех пользователей с активными токенами
        users_notified = set()
        for push_token in active_tokens:
            if push_token.user_id not in users_notified:
                Notification.objects.create(
                    user=push_token.user,
                    title=title,
                    message=message,
                    notification_type='SYSTEM',
                    is_sent=False
                )
                users_notified.add(push_token.user_id)
        
        # Собираем информацию об устройствах
        devices = list(active_tokens.values_list('device_type', flat=True).distinct())
        
        # Отправляем push-уведомления через Firebase
        tokens = list(active_tokens.values_list('token', flat=True))
        
        if tokens:
            try:
                result = send_push_notification_multicast(
                    tokens=tokens,
                    title=title,
                    message=message,
                    data={'type': 'test_notification'}
                )
                
                # Помечаем уведомления как отправленные
                Notification.objects.filter(
                    title=title,
                    message=message,
                    is_sent=False
                ).update(
                    is_sent=True,
                    sent_at=timezone.now()
                )
                
                return Response({
                    'status': 'success',
                    'sent_count': len(users_notified),
                    'devices': devices,
                    'push_success_count': result['success_count'],
                    'push_failure_count': result['failure_count'],
                    'message': f'Отправлено {result["success_count"]} push-уведомлений'
                })
                
            except Exception as e:
                return Response({
                    'status': 'partial_success',
                    'sent_count': len(users_notified),
                    'devices': devices,
                    'push_error': str(e),
                    'message': 'Уведомления созданы в базе, но push-отправка не удалась'
                })
        
        return Response({
            'status': 'success',
            'sent_count': len(users_notified),
            'devices': devices
        })