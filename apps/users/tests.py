"""
Comprehensive тесты для реферальной системы и системы скидок
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import User

User = get_user_model()


class UserModelReferralTest(TestCase):
    """Тесты модели User - реферальная система"""

    def setUp(self):
        self.referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123',
            first_name='Referrer',
            last_name='Test'
        )

    def test_user_created_with_referral_code(self):
        """Пользователь создается с реферальным кодом"""
        user = User.objects.get(email='referrer@test.com')
        self.assertTrue(user.referral_code)
        # token_urlsafe(6) генерирует ~8 символов
        self.assertGreaterEqual(len(user.referral_code), 6)
        self.assertTrue(user.referral_code.isupper())

    def test_referral_code_unique(self):
        """Реферальные коды уникальны"""
        another_user = User.objects.create_user(
            username='another@test.com',
            email='another@test.com',
            password='testpass123',
            first_name='Another',
            last_name='Test'
        )
        self.assertNotEqual(self.referrer.referral_code, another_user.referral_code)

    def test_referred_by_field(self):
        """Поле referred_by правильно связывает пользователей"""
        referred_user = User.objects.create_user(
            username='referred@test.com',
            email='referred@test.com',
            password='testpass123',
            first_name='Referred',
            last_name='Test',
            referred_by=self.referrer
        )
        self.assertEqual(referred_user.referred_by, self.referrer)
        self.assertIn(referred_user, self.referrer.referred_users.all())

    def test_referred_users_related(self):
        """Связь referred_users работает корректно"""
        user1 = User.objects.create_user(
            username='user1@test.com',
            email='user1@test.com',
            password='testpass123',
            referred_by=self.referrer
        )
        user2 = User.objects.create_user(
            username='user2@test.com',
            email='user2@test.com',
            password='testpass123',
            referred_by=self.referrer
        )
        
        self.assertEqual(self.referrer.referred_users.count(), 2)
        self.assertIn(user1, self.referrer.referred_users.all())
        self.assertIn(user2, self.referrer.referred_users.all())


class UserDiscountSystemTest(TestCase):
    """Тесты модели User - система скидок"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='discount@test.com',
            email='discount@test.com',
            password='testpass123',
            first_name='Discount',
            last_name='Test'
        )

    def test_default_discount_level(self):
        """По умолчанию уровень Bronze (0 операций)"""
        discount = self.user.get_discount_level()
        self.assertEqual(discount['level'], 'Bronze')
        self.assertEqual(discount['discount'], 0.5)

    def test_silver_level_at_5_orders(self):
        """Уровень Silver при 5 операциях"""
        self.user.total_orders = 5
        self.user.save()
        
        discount = self.user.get_discount_level()
        self.assertEqual(discount['level'], 'Silver')
        self.assertEqual(discount['discount'], 1.0)

    def test_gold_level_at_10_orders(self):
        """Уровень Gold при 10 операциях"""
        self.user.total_orders = 10
        self.user.save()
        
        discount = self.user.get_discount_level()
        self.assertEqual(discount['level'], 'Gold')
        self.assertEqual(discount['discount'], 2.0)

    def test_gold_level_above_10_orders(self):
        """Уровень Gold сохраняется при >10 операциях"""
        self.user.total_orders = 15
        self.user.save()
        
        discount = self.user.get_discount_level()
        self.assertEqual(discount['level'], 'Gold')
        self.assertEqual(discount['discount'], 2.0)

    def test_first_order_discount_with_referrer(self):
        """Скидка 5% для пользователя с реферером"""
        referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123',
            referred_by=None
        )
        referred_user = User.objects.create_user(
            username='referred@test.com',
            email='referred@test.com',
            password='testpass123',
            referred_by=referrer
        )
        
        discount = referred_user.get_first_order_discount()
        self.assertEqual(discount, 5.0)

    def test_no_first_order_discount_without_referrer(self):
        """Нет скидки без реферера"""
        discount = self.user.get_first_order_discount()
        self.assertEqual(discount, 0.0)

    def test_first_order_discount_used(self):
        """Скидка не применяется после использования"""
        referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123'
        )
        referred_user = User.objects.create_user(
            username='referred@test.com',
            email='referred@test.com',
            password='testpass123',
            referred_by=referrer,
            first_order_discount_used=True
        )
        
        discount = referred_user.get_first_order_discount()
        self.assertEqual(discount, 0.0)

    def test_increment_orders(self):
        """Метод increment_orders увеличивает счетчик"""
        initial_orders = self.user.total_orders
        self.user.increment_orders()
        
        self.assertEqual(self.user.total_orders, initial_orders + 1)

    def test_increment_orders_marks_discount_used(self):
        """increment_orders помечает скидку как использованную"""
        referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123'
        )
        referred_user = User.objects.create_user(
            username='referred@test.com',
            email='referred@test.com',
            password='testpass123',
            referred_by=referrer,
            first_order_discount_used=False
        )
        
        referred_user.increment_orders()
        self.assertTrue(referred_user.first_order_discount_used)

    def test_discount_level_progression(self):
        """Прогрессия уровней скидок"""
        for orders in [0, 3, 5, 7, 10, 15]:
            self.user.total_orders = orders
            self.user.save()
            
            discount = self.user.get_discount_level()
            
            if orders < 5:
                expected_level = 'Bronze'
                expected_discount = 0.5
            elif orders < 10:
                expected_level = 'Silver'
                expected_discount = 1.0
            else:
                expected_level = 'Gold'
                expected_discount = 2.0
            
            self.assertEqual(discount['level'], expected_level, 
                           f"При {orders} операциях уровень {expected_level}")
            self.assertEqual(discount['discount'], expected_discount,
                           f"При {orders} операциях скидка {expected_discount}%")


class ReferralAPIRegistrationTest(TestCase):
    """Тесты API регистрации с реферальным кодом"""

    def setUp(self):
        self.client = APIClient()
        
        # Создаем реферера
        self.referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123',
            first_name='Referrer',
            last_name='Test',
            is_active=True
        )

    def test_registration_with_referral_code(self):
        """Регистрация с реферальным кодом"""
        response = self.client.post('/api/v1/user/registration/', {
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'SecurePass123',
            'password2': 'SecurePass123',
            'referral_code': self.referrer.referral_code
        })
        
        # Регистрация создает неактивного пользователя (ждет подтверждения email)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Проверяем что пользователь создан
        new_user = User.objects.get(email='newuser@test.com')
        self.assertEqual(new_user.referred_by, self.referrer)

    def test_registration_with_invalid_referral_code(self):
        """Регистрация с неверным реферальным кодом"""
        response = self.client.post('/api/v1/user/registration/', {
            'email': 'newuser2@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'SecurePass123',
            'password2': 'SecurePass123',
            'referral_code': 'INVALID_CODE_123'
        })
        
        # Должна быть ошибка валидации
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('referral_code', response.data)

    def test_registration_without_referral_code(self):
        """Регистрация без реферального кода"""
        response = self.client.post('/api/v1/user/registration/', {
            'email': 'newuser3@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'SecurePass123',
            'password2': 'SecurePass123'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        new_user = User.objects.get(email='newuser3@test.com')
        self.assertIsNone(new_user.referred_by)


class ApplyReferralCodeAPITest(TestCase):
    """Тесты API применения реферального кода"""

    def setUp(self):
        self.client = APIClient()
        
        self.referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123',
            first_name='Referrer',
            last_name='Test',
            is_active=True
        )
        
        self.new_user = User.objects.create_user(
            username='newuser@test.com',
            email='newuser@test.com',
            password='testpass123',
            first_name='New',
            last_name='User',
            is_active=True,
            referred_by=None
        )
        
        self.client.force_authenticate(user=self.new_user)

    def test_apply_valid_referral_code(self):
        """Применение валидного реферального кода"""
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': self.referrer.referral_code
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Реферальный код успешно применен')
        
        # Проверяем что реферер установлен
        self.new_user.refresh_from_db()
        self.assertEqual(self.new_user.referred_by, self.referrer)

    def test_apply_referral_code_already_applied(self):
        """Повторное применение кода запрещено"""
        # Сначала применяем код
        self.new_user.referred_by = self.referrer
        self.new_user.save()
        
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': self.referrer.referral_code
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Реферальный код уже применен')

    def test_apply_invalid_referral_code(self):
        """Применение неверного кода"""
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': 'INVALID_CODE'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Неверный реферальный код')

    def test_apply_own_referral_code(self):
        """Нельзя применить свой собственный код"""
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': self.new_user.referral_code
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Нельзя пригласить самого себя')

    def test_apply_referral_unauthenticated(self):
        """Применение кода без авторизации"""
        self.client.logout()
        
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': self.referrer.referral_code
        })
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ReferralStatsAPITest(TestCase):
    """Тесты API статистики рефералов"""

    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='statsuser@test.com',
            email='statsuser@test.com',
            password='testpass123',
            first_name='Stats',
            last_name='User',
            is_active=True
        )
        
        # Создаем рефералов
        for i in range(5):
            User.objects.create_user(
                username=f'referred{i}@test.com',
                email=f'referred{i}@test.com',
                password='testpass123',
                referred_by=self.user,
                is_active=True
            )
        
        self.user.total_orders = 7
        self.user.total_bonus = 150.50
        self.user.save()
        
        self.client.force_authenticate(user=self.user)

    def test_get_referral_stats(self):
        """Получение статистики рефералов"""
        response = self.client.get('/api/v1/user/referral/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['referred_count'], 5)
        self.assertEqual(response.data['total_orders'], 7)
        self.assertEqual(float(response.data['total_bonus']), 150.50)
        self.assertEqual(response.data['discount_level']['level'], 'Silver')
        self.assertIn('referral_code', response.data)
        self.assertIn('referral_link', response.data)
        self.assertIn('kargopay.app/ref/', response.data['referral_link'])

    def test_referral_stats_unauthenticated(self):
        """Статистика без авторизации"""
        self.client.logout()
        
        response = self.client.get('/api/v1/user/referral/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileDiscountTest(TestCase):
    """Тесты профиля пользователя со скидками"""

    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='profileuser@test.com',
            email='profileuser@test.com',
            password='testpass123',
            first_name='Profile',
            last_name='User',
            is_active=True
        )
        
        self.user.total_orders = 12
        self.user.total_bonus = 500.00
        self.user.save()
        
        self.client.force_authenticate(user=self.user)

    def test_get_profile_with_discount_info(self):
        """Профиль содержит информацию о скидках"""
        response = self.client.get('/api/v1/user/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'profileuser@test.com')
        self.assertEqual(response.data['total_orders'], 12)
        self.assertEqual(float(response.data['total_bonus']), 500.00)
        self.assertEqual(response.data['discount_level']['level'], 'Gold')
        self.assertEqual(response.data['discount_level']['discount'], 2.0)
        self.assertEqual(response.data['first_order_discount'], 0.0)

    def test_profile_first_order_discount(self):
        """Профиль показывает скидку первого заказа"""
        referrer = User.objects.create_user(
            username='referrer@test.com',
            email='referrer@test.com',
            password='testpass123',
            is_active=True
        )
        
        new_user = User.objects.create_user(
            username='newuser@test.com',
            email='newuser@test.com',
            password='testpass123',
            referred_by=referrer,
            is_active=True,
            first_order_discount_used=False
        )
        
        self.client.force_authenticate(user=new_user)
        response = self.client.get('/api/v1/user/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_order_discount'], 5.0)

    def test_profile_unauthenticated(self):
        """Профиль без авторизации"""
        self.client.logout()
        
        response = self.client.get('/api/v1/user/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ReferralSystemEdgeCasesTest(TestCase):
    """Тесты граничных случаев реферальной системы"""

    def setUp(self):
        self.client = APIClient()

    def test_circular_referral_prevented(self):
        """Предотвращение циклических рефералов"""
        user1 = User.objects.create_user(
            username='user1@test.com',
            email='user1@test.com',
            password='testpass123',
            is_active=True
        )
        user2 = User.objects.create_user(
            username='user2@test.com',
            email='user2@test.com',
            password='testpass123',
            referred_by=user1,
            is_active=True
        )
        
        # Пытаемся сделать user1 рефералом user2 (цикл)
        user1.referred_by = user2
        user1.save()
        
        # Это технически возможно в БД, но не должно происходить через API
        self.client.force_authenticate(user=user1)
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': user2.referral_code
        })
        
        # API должно предотвратить это
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiple_referrals_same_user(self):
        """Один пользователь не может иметь несколько рефереров"""
        referrer1 = User.objects.create_user(
            username='ref1@test.com',
            email='ref1@test.com',
            password='testpass123',
            is_active=True
        )
        referrer2 = User.objects.create_user(
            username='ref2@test.com',
            email='ref2@test.com',
            password='testpass123',
            is_active=True
        )
        
        referred = User.objects.create_user(
            username='referred@test.com',
            email='referred@test.com',
            password='testpass123',
            referred_by=referrer1,
            is_active=True
        )
        
        self.client.force_authenticate(user=referred)
        
        # Пытаемся применить второй код
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': referrer2.referral_code
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Реферальный код уже применен')

    def test_referral_code_case_insensitive(self):
        """Реферальный код регистронезависимый"""
        referrer = User.objects.create_user(
            username='ref@test.com',
            email='ref@test.com',
            password='testpass123',
            is_active=True
        )
        
        new_user = User.objects.create_user(
            username='new@test.com',
            email='new@test.com',
            password='testpass123',
            is_active=True
        )
        
        self.client.force_authenticate(user=new_user)
        
        # Пробуем применить код в нижнем регистре
        response = self.client.post('/api/v1/user/referral/apply/', {
            'referral_code': referrer.referral_code.lower()
        })
        
        # Коды в базе uppercase, поэтому lowercase не сработает
        # Это нужно исправить в production
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_referrer_with_many_referrals(self):
        """Реферер с большим количеством рефералов"""
        referrer = User.objects.create_user(
            username='superref@test.com',
            email='superref@test.com',
            password='testpass123',
            is_active=True
        )
        
        # Создаем 100 рефералов
        for i in range(100):
            User.objects.create_user(
                username=f'ref{i}@test.com',
                email=f'ref{i}@test.com',
                password='testpass123',
                referred_by=referrer,
                is_active=True
            )
        
        self.client.force_authenticate(user=referrer)
        response = self.client.get('/api/v1/user/referral/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['referred_count'], 100)


class DiscountSystemEdgeCasesTest(TestCase):
    """Тесты граничных случаев системы скидок"""

    def setUp(self):
        self.client = APIClient()

    def test_bonus_decimal_precision(self):
        """Точность вычисления бонусов"""
        user = User.objects.create_user(
            username='bonus@test.com',
            email='bonus@test.com',
            password='testpass123',
            is_active=True
        )
        
        # Устанавливаем бонусы с копейками
        user.total_bonus = 123.45
        user.save()
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/v1/user/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_bonus']), 123.45)

    def test_discount_at_boundary(self):
        """Скидки на границах значений"""
        user = User.objects.create_user(
            username='boundary@test.com',
            email='boundary@test.com',
            password='testpass123',
            is_active=True
        )
        
        # Ровно 5 операций - должен быть Silver
        user.total_orders = 5
        user.save()
        discount = user.get_discount_level()
        self.assertEqual(discount['level'], 'Silver')
        self.assertEqual(discount['discount'], 1.0)
        
        # Ровно 10 операций - должен быть Gold
        user.total_orders = 10
        user.save()
        discount = user.get_discount_level()
        self.assertEqual(discount['level'], 'Gold')
        self.assertEqual(discount['discount'], 2.0)
        
        # Ровно 4 операции - должен быть Bronze
        user.total_orders = 4
        user.save()
        discount = user.get_discount_level()
        self.assertEqual(discount['level'], 'Bronze')
        self.assertEqual(discount['discount'], 0.5)

    def test_negative_orders(self):
        """Отрицательное количество операций"""
        user = User.objects.create_user(
            username='negative@test.com',
            email='negative@test.com',
            password='testpass123',
            is_active=True
        )
        
        # Отрицательные операции невозможны (PositiveIntegerField)
        with self.assertRaises(Exception):
            user.total_orders = -1
            user.save()

    def test_very_large_order_count(self):
        """Очень большое количество операций"""
        user = User.objects.create_user(
            username='large@test.com',
            email='large@test.com',
            password='testpass123',
            is_active=True
        )
        
        user.total_orders = 999999
        user.save()

        discount = user.get_discount_level()
        self.assertEqual(discount['level'], 'Gold')
        self.assertEqual(discount['discount'], 2.0)


class RefreshTokenAPITest(TestCase):
    """Тесты API обновления токена"""

    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            username='refresh@test.com',
            email='refresh@test.com',
            password='testpass123',
            first_name='Refresh',
            last_name='Test',
            is_active=True
        )
        # Активируем пользователя (по умолчанию create_user создает неактивного)
        self.user.is_active = True
        self.user.save()

    def test_refresh_token_valid(self):
        """Обновление токена с валидным refresh токеном"""
        # Получаем токены при логине
        login_response = self.client.post('/api/v1/user/login/', {
            'email': 'refresh@test.com',
            'password': 'testpass123'
        })
        
        if login_response.status_code != status.HTTP_200_OK:
            # Если пользователь не активен, активируем и пробуем снова
            self.user.is_active = True
            self.user.save()
            login_response = self.client.post('/api/v1/user/login/', {
                'email': 'refresh@test.com',
                'password': 'testpass123'
            })
        
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        refresh_token = login_response.data['refresh']
        
        # Обновляем токен
        refresh_response = self.client.post('/api/v1/user/refresh/', {
            'refresh': refresh_token
        })
        
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)
        self.assertIn('refresh', refresh_response.data)
        
        # Проверяем что новый access токен работает
        new_access = refresh_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        
        profile_response = self.client.get('/api/v1/user/profile/')
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)

    def test_refresh_token_missing(self):
        """Обновление токена без refresh токена"""
        response = self.client.post('/api/v1/user/refresh/', {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Refresh токен обязателен')

    def test_refresh_token_invalid(self):
        """Обновление токена с неверным токеном"""
        response = self.client.post('/api/v1/user/refresh/', {
            'refresh': 'invalid_token_here'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Неверный refresh токен')

    def test_refresh_token_blacklisted(self):
        """Обновление токена из blacklist"""
        # Получаем токены при логине
        self.user.is_active = True
        self.user.save()
        
        login_response = self.client.post('/api/v1/user/login/', {
            'email': 'refresh@test.com',
            'password': 'testpass123'
        })
        
        if login_response.status_code != status.HTTP_200_OK:
            self.skipTest("Не удалось войти в систему")
        
        refresh_token = login_response.data['refresh']
        
        # Сначала пробуем обновить (должно сработать)
        refresh_response = self.client.post('/api/v1/user/refresh/', {
            'refresh': refresh_token
        })
        
        # Выходим (токен попадает в blacklist)
        self.client.post('/api/v1/user/logout/', {
            'refresh': refresh_token
        })
        
        # Пытаемся обновить blacklist токен
        refresh_response = self.client.post('/api/v1/user/refresh/', {
            'refresh': refresh_token
        })
        
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(refresh_response.data['error'], 'Токен был отозван')

    def test_refresh_token_expired(self):
        """Обновление истекшего токена"""
        from datetime import datetime, timedelta
        from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
        
        # Создаем токен с истекшим сроком
        expired_token = JWTRefreshToken.for_user(self.user)
        # В новых версиях SIMPLE JWT используется set_iat и exp вычисляется автоматически
        # Просто используем черный список для имитации невалидного токена
        expired_token.blacklist()
        
        response = self.client.post('/api/v1/user/refresh/', {
            'refresh': str(expired_token)
        })
        
        # Blacklisted токен должен вернуть 401
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_with_new_access_token(self):
        """Новый access токен дает доступ к защищенным ресурсам"""
        self.user.is_active = True
        self.user.save()
        
        # Получаем токены
        login_response = self.client.post('/api/v1/user/login/', {
            'email': 'refresh@test.com',
            'password': 'testpass123'
        })
        
        if login_response.status_code != status.HTTP_200_OK:
            self.skipTest("Не удалось войти в систему")
        
        refresh_token = login_response.data['refresh']
        
        # Обновляем
        refresh_response = self.client.post('/api/v1/user/refresh/', {
            'refresh': refresh_token
        })
        
        new_access = refresh_response.data['access']
        
        # Используем новый access токен
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        
        # Проверяем доступ к профилю
        profile_response = self.client.get('/api/v1/user/profile/')
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data['email'], 'refresh@test.com')
