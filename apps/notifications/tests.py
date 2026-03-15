from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Notification, PushToken

User = get_user_model()


class NotificationModelTest(TestCase):
    """Тесты для модели Notification"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_create_notification(self):
        """Создание уведомления"""
        notification = Notification.objects.create(
            user=self.user,
            title='Test Notification',
            message='This is a test message',
            notification_type='SYSTEM'
        )
        self.assertEqual(str(notification), 'Test Notification - test@example.com')
        self.assertFalse(notification.is_read)
        self.assertFalse(notification.is_sent)

    def test_notification_ordering(self):
        """Уведомления сортируются по убыванию created_at"""
        n1 = Notification.objects.create(
            user=self.user,
            title='First',
            message='First message',
            notification_type='SYSTEM'
        )
        n2 = Notification.objects.create(
            user=self.user,
            title='Second',
            message='Second message',
            notification_type='SYSTEM'
        )
        notifications = list(Notification.objects.filter(user=self.user))
        self.assertEqual(notifications[0], n2)
        self.assertEqual(notifications[1], n1)

    def test_notification_type_choices(self):
        """Проверка типов уведомлений"""
        valid_types = [
            'ORDER_CREATED', 'ORDER_COMPLETED', 'ORDER_REJECTED',
            'BONUS_RECEIVED', 'PROMO', 'SYSTEM'
        ]
        for notif_type in valid_types:
            notification = Notification.objects.create(
                user=self.user,
                title='Test',
                message='Test message',
                notification_type=notif_type
            )
            self.assertEqual(notification.notification_type, notif_type)


class PushTokenModelTest(TestCase):
    """Тесты для модели PushToken"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_create_push_token(self):
        """Создание push-токена"""
        token = PushToken.objects.create(
            user=self.user,
            token='fcm_token_12345',
            device_type='android',
            device_info='Samsung Galaxy S24'
        )
        self.assertEqual(str(token), 'test@example.com - android')
        self.assertTrue(token.is_active)
        self.assertIsNone(token.last_used_at)

    def test_unique_token(self):
        """Токен должен быть уникальным"""
        PushToken.objects.create(
            user=self.user,
            token='unique_token',
            device_type='web'
        )
        with self.assertRaises(Exception):
            PushToken.objects.create(
                user=self.user,
                token='unique_token',
                device_type='ios'
            )


class NotificationListViewTest(TestCase):
    """Тесты для NotificationListView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user2 = User.objects.create_user(
            username='test2@example.com',
            email='test2@example.com',
            password='testpass123',
            first_name='Test2',
            last_name='User2'
        )

    def test_get_notifications_authenticated(self):
        """Получение списка уведомлений авторизованным пользователем"""
        Notification.objects.create(
            user=self.user,
            title='Test Notification',
            message='Test message',
            notification_type='SYSTEM'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # С группировкой по датам данные находятся в 'groups'
        self.assertIn('groups', response.data)
        self.assertGreater(len(response.data['groups']), 0)

    def test_get_notifications_unauthenticated(self):
        """Получение списка уведомлений неавторизованным пользователем"""
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_only_user_notifications(self):
        """Пользователь видит только свои уведомления"""
        Notification.objects.create(
            user=self.user,
            title='User 1 Notification',
            message='Message for user 1',
            notification_type='SYSTEM'
        )
        Notification.objects.create(
            user=self.user2,
            title='User 2 Notification',
            message='Message for user 2',
            notification_type='SYSTEM'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Проверяем что есть группы
        self.assertIn('groups', response.data)
        self.assertGreater(len(response.data['groups']), 0)
        # Проверяем что в первой группе есть наше уведомление
        first_group_items = response.data['groups'][0]['items']
        self.assertEqual(len(first_group_items), 1)
        self.assertEqual(first_group_items[0]['title'], 'User 1 Notification')

    def test_notifications_ordering(self):
        """Уведомления возвращаются в порядке убывания created_at"""
        n1 = Notification.objects.create(
            user=self.user,
            title='First',
            message='First message',
            notification_type='SYSTEM'
        )
        n2 = Notification.objects.create(
            user=self.user,
            title='Second',
            message='Second message',
            notification_type='SYSTEM'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Проверяем что группы есть
        self.assertGreater(len(response.data['groups']), 0)
        # Оба уведомления должны быть в группе "Сегодня"
        today_group = response.data['groups'][0]
        self.assertEqual(today_group['date'], 'Сегодня')
        # Первое уведомление в группе должно быть новее (Second)
        self.assertEqual(today_group['items'][0]['title'], 'Second')


class UnreadNotificationCountViewTest(TestCase):
    """Тесты для UnreadNotificationCountView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_get_unread_count(self):
        """Получение количества непрочитанных уведомлений"""
        Notification.objects.create(
            user=self.user,
            title='Unread 1',
            message='Message',
            notification_type='SYSTEM',
            is_read=False
        )
        Notification.objects.create(
            user=self.user,
            title='Unread 2',
            message='Message',
            notification_type='SYSTEM',
            is_read=False
        )
        Notification.objects.create(
            user=self.user,
            title='Read 1',
            message='Message',
            notification_type='SYSTEM',
            is_read=True
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 2)

    def test_get_unread_count_zero(self):
        """Нулевое количество непрочитанных уведомлений"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 0)

    def test_get_unread_count_unauthenticated(self):
        """Получение количества непрочитанных уведомлений неавторизованным"""
        response = self.client.get('/api/v1/notifications/unread-count/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationMarkAsReadViewTest(TestCase):
    """Тесты для NotificationMarkAsReadView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user2 = User.objects.create_user(
            username='test2@example.com',
            email='test2@example.com',
            password='testpass123',
            first_name='Test2',
            last_name='User2'
        )

    def test_mark_notification_read(self):
        """Отметка уведомления как прочитанного"""
        notification = Notification.objects.create(
            user=self.user,
            title='Test',
            message='Message',
            notification_type='SYSTEM',
            is_read=False
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/v1/notifications/{notification.id}/read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_notification_not_found(self):
        """Уведомление не найдено"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/notifications/999/read/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'Уведомление не найдено')

    def test_mark_other_user_notification(self):
        """Попытка отметить уведомление другого пользователя"""
        notification = Notification.objects.create(
            user=self.user2,
            title='Test',
            message='Message',
            notification_type='SYSTEM',
            is_read=False
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/v1/notifications/{notification.id}/read/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_read_unauthenticated(self):
        """Отметка уведомления неавторизованным пользователем"""
        response = self.client.post('/api/v1/notifications/1/read/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationMarkAllAsReadViewTest(TestCase):
    """Тесты для NotificationMarkAllAsReadView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_mark_all_read(self):
        """Отметка всех уведомлений как прочитанные"""
        Notification.objects.create(
            user=self.user,
            title='Unread 1',
            message='Message',
            notification_type='SYSTEM',
            is_read=False
        )
        Notification.objects.create(
            user=self.user,
            title='Unread 2',
            message='Message',
            notification_type='SYSTEM',
            is_read=False
        )
        Notification.objects.create(
            user=self.user,
            title='Already Read',
            message='Message',
            notification_type='SYSTEM',
            is_read=True
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/notifications/mark-all-read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        unread_count = Notification.objects.filter(
            user=self.user,
            is_read=False
        ).count()
        self.assertEqual(unread_count, 0)

    def test_mark_all_read_unauthenticated(self):
        """Отметка всех уведомлений неавторизованным пользователем"""
        response = self.client.post('/api/v1/notifications/mark-all-read/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PushTokenRegisterViewTest(TestCase):
    """Тесты для PushTokenRegisterView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_register_push_token(self):
        """Регистрация push-токена"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/push-token/register/', {
            'token': 'fcm_token_12345',
            'device_type': 'android',
            'device_info': 'Samsung Galaxy S24'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['token'], 'fcm_token_12345')
        self.assertEqual(response.data['device_type'], 'android')
        self.assertEqual(response.data['device_info'], 'Samsung Galaxy S24')
        self.assertEqual(PushToken.objects.count(), 1)

    def test_register_push_token_missing_token(self):
        """Регистрация без токена"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/push-token/register/', {
            'device_type': 'android'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', response.data)

    def test_register_push_token_update_existing(self):
        """Обновление существующего токена"""
        PushToken.objects.create(
            user=self.user,
            token='fcm_token_12345',
            device_type='web',
            device_info='Chrome'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/push-token/register/', {
            'token': 'fcm_token_12345',
            'device_type': 'android',
            'device_info': 'Samsung Galaxy S24'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PushToken.objects.count(), 1)
        token = PushToken.objects.get(token='fcm_token_12345')
        self.assertEqual(token.device_type, 'android')
        self.assertEqual(token.device_info, 'Samsung Galaxy S24')

    def test_register_push_token_unauthenticated(self):
        """Регистрация токена неавторизованным пользователем"""
        response = self.client.post('/api/v1/push-token/register/', {
            'token': 'fcm_token_12345',
            'device_type': 'android'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PushTokenDeleteViewTest(TestCase):
    """Тесты для PushTokenDeleteView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user2 = User.objects.create_user(
            username='test2@example.com',
            email='test2@example.com',
            password='testpass123',
            first_name='Test2',
            last_name='User2'
        )

    def test_delete_push_token(self):
        """Удаление push-токена"""
        PushToken.objects.create(
            user=self.user,
            token='fcm_token_12345',
            device_type='android'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/push-token/delete/', {
            'token': 'fcm_token_12345'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(PushToken.objects.count(), 0)

    def test_delete_other_user_token(self):
        """Попытка удалить токен другого пользователя"""
        PushToken.objects.create(
            user=self.user2,
            token='fcm_token_12345',
            device_type='android'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/push-token/delete/', {
            'token': 'fcm_token_12345'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PushToken.objects.count(), 1)

    def test_delete_push_token_missing_token(self):
        """Удаление без указания токена"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/push-token/delete/', {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

    def test_delete_push_token_unauthenticated(self):
        """Удаление токена неавторизованным пользователем"""
        response = self.client.post('/api/v1/push-token/delete/', {
            'token': 'fcm_token_12345'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SendTestNotificationViewTest(TestCase):
    """Тесты для SendTestNotificationView"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user2 = User.objects.create_user(
            username='test2@example.com',
            email='test2@example.com',
            password='testpass123',
            first_name='Test2',
            last_name='User2'
        )

    def test_send_test_notification(self):
        """Отправка тестового уведомления"""
        PushToken.objects.create(
            user=self.user,
            token='fcm_token_1',
            device_type='android',
            is_active=True
        )
        PushToken.objects.create(
            user=self.user,
            token='fcm_token_2',
            device_type='web',
            is_active=True
        )
        PushToken.objects.create(
            user=self.user2,
            token='fcm_token_3',
            device_type='ios',
            is_active=True
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/send-test-notification/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['sent_count'], 2)
        self.assertIn('android', response.data['devices'])
        self.assertIn('web', response.data['devices'])
        
        # Проверяем что уведомления созданы
        self.assertEqual(Notification.objects.count(), 2)

    def test_send_test_notification_custom_text(self):
        """Отправка тестового уведомления с кастомным текстом"""
        PushToken.objects.create(
            user=self.user,
            token='fcm_token_1',
            device_type='android',
            is_active=True
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/send-test-notification/', {
            'title': '🎉 Custom Title',
            'message': 'Custom message'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        notification = Notification.objects.first()
        self.assertEqual(notification.title, '🎉 Custom Title')
        self.assertEqual(notification.message, 'Custom message')

    def test_send_test_notification_no_active_tokens(self):
        """Отправка при отсутствии активных токенов"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/send-test-notification/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sent_count'], 0)
        self.assertEqual(response.data['devices'], [])

    def test_send_test_notification_inactive_tokens(self):
        """Отправка при неактивных токенах"""
        PushToken.objects.create(
            user=self.user,
            token='fcm_token_1',
            device_type='android',
            is_active=False
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v1/send-test-notification/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sent_count'], 0)

    def test_send_test_notification_unauthenticated(self):
        """Отправка уведомления неавторизованным пользователем"""
        response = self.client.post('/api/v1/send-test-notification/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
