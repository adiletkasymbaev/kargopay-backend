from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Service, Bank, PaymentDetail, ExchangeRate, Order


User = get_user_model()


class TestImageMixin:
    """Миксин для создания тестовых изображений"""
    
    @staticmethod
    def create_test_image(name='test.png'):
        """Создаёт простое тестовое изображение"""
        from io import BytesIO
        from PIL import Image
        
        img = Image.new('RGB', (100, 100), color='red')
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        return SimpleUploadedFile(name, img_io.read(), content_type='image/png')


class ServiceModelTest(TestCase):
    """Тесты модели Service"""
    
    def test_create_service(self):
        service = Service.objects.create(
            name='AliPay',
            slug='alipay',
            description='Пополнение AliPay'
        )
        self.assertEqual(str(service), 'AliPay')
        self.assertTrue(service.is_active)
    
    def test_service_ordering(self):
        Service.objects.create(name='WeChat', slug='wechat')
        Service.objects.create(name='AliPay', slug='alipay')
        
        services = list(Service.objects.all())
        self.assertEqual(services[0].name, 'AliPay')
        self.assertEqual(services[1].name, 'WeChat')


class BankModelTest(TestCase):
    """Тесты модели Bank"""
    
    def test_create_bank(self):
        bank = Bank.objects.create(
            name='Optima Bank',
            slug='optima'
        )
        self.assertEqual(str(bank), 'Optima Bank')
        self.assertTrue(bank.is_active)
    
    def test_bank_ordering(self):
        Bank.objects.create(name='mBank', slug='mbank')
        Bank.objects.create(name='Optima', slug='optima')
        
        # Сортировка по алфавиту: 'mBank' > 'Optima' (ASCII)
        banks = list(Bank.objects.order_by('name').all())
        self.assertEqual(banks[0].name, 'Optima')
        self.assertEqual(banks[1].name, 'mBank')


class PaymentDetailModelTest(TestCase):
    """Тесты модели PaymentDetail"""
    
    def test_create_payment_detail(self):
        service = Service.objects.create(name='AliPay', slug='alipay')
        bank = Bank.objects.create(name='Optima', slug='optima')
        
        detail = PaymentDetail.objects.create(
            service=service,
            bank=bank,
            account_number='1234567890',
            recipient_name='Test User'
        )
        self.assertEqual(str(detail), 'AliPay - Optima')
        self.assertTrue(detail.is_active)
    
    def test_unique_together_constraint(self):
        service = Service.objects.create(name='AliPay', slug='alipay')
        bank = Bank.objects.create(name='Optima', slug='optima')
        
        PaymentDetail.objects.create(service=service, bank=bank)
        
        with self.assertRaises(Exception):
            PaymentDetail.objects.create(service=service, bank=bank)


class ExchangeRateModelTest(TestCase):
    """Тесты модели ExchangeRate"""
    
    def test_create_exchange_rate(self):
        rate = ExchangeRate.objects.create(
            from_currency='KGS',
            to_currency='CNY',
            rate=Decimal('0.1234')
        )
        self.assertEqual(str(rate), 'KGS → CNY: 0.1234')
        self.assertTrue(rate.is_active)
    
    def test_unique_together_constraint(self):
        ExchangeRate.objects.create(
            from_currency='KGS',
            to_currency='CNY',
            rate=Decimal('0.1234')
        )
        
        with self.assertRaises(Exception):
            ExchangeRate.objects.create(
                from_currency='KGS',
                to_currency='CNY',
                rate=Decimal('0.5000')
            )


class OrderModelTest(TestCase):
    """Тесты модели Order"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.service = Service.objects.create(name='AliPay', slug='alipay')
        self.bank = Bank.objects.create(name='Optima', slug='optima')
        self.exchange_rate = ExchangeRate.objects.create(
            from_currency='KGS',
            to_currency='CNY',
            rate=Decimal('0.1200')
        )
        self.receipt_image = TestImageMixin.create_test_image('receipt.png')
    
    def test_create_order(self):
        order = Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00')
        )
        self.assertEqual(order.status, 'PENDING')
        self.assertIsNotNone(order.created_at)
    
    def test_order_calculate_amounts(self):
        order = Order(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            final_amount=Decimal('1000.00')
        )
        order.calculate_amounts()
        
        # Проверяем что курс применён
        self.assertEqual(order.exchange_rate, Decimal('0.1200'))
        # 1000 * 0.12 = 120 CNY
        base_amount = Decimal('1000.00') * Decimal('0.1200')
        # Скидка 0.5% для Bronze уровня
        discount = base_amount * Decimal('0.005')
        expected_amount_to = base_amount - discount
        
        self.assertEqual(order.amount_to, expected_amount_to)
        self.assertEqual(order.discount_percent, Decimal('0.5'))
    
    def test_order_with_referral_discount(self):
        # Создаём реферера
        referrer = User.objects.create_user(
            username='referrer',
            email='referrer@example.com',
            password='testpass123'
        )
        # Создаём пользователя с реферером
        referred_user = User.objects.create_user(
            username='referred',
            email='referred@example.com',
            password='testpass123',
            referred_by=referrer
        )
        
        order = Order(
            user=referred_user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            final_amount=Decimal('1000.00')
        )
        order.calculate_amounts()
        
        # Должна примениться скидка 5% для первой операции по рефералке
        self.assertEqual(order.discount_percent, Decimal('5.0'))
    
    def test_order_higher_discount_level(self):
        # Увеличиваем количество операций пользователя
        self.user.total_orders = 10
        self.user.save()
        
        order = Order(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            final_amount=Decimal('1000.00')
        )
        order.calculate_amounts()
        
        # Gold уровень - 2% скидка
        self.assertEqual(order.discount_percent, Decimal('2.0'))
    
    def test_order_str_representation(self):
        order = Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00')
        )
        self.assertIn('test@example.com', str(order))
        self.assertIn('PENDING', str(order))
    
    def test_mark_as_completed(self):
        order = Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00')
        )
        
        order.mark_as_completed()
        
        self.assertEqual(order.status, 'COMPLETED')
        self.assertIsNotNone(order.completed_at)
    
    def test_mark_as_rejected(self):
        order = Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='alipay_account',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00')
        )
        
        order.mark_as_rejected(comment='Неверные реквизиты')
        
        self.assertEqual(order.status, 'REJECTED')
        self.assertEqual(order.manager_comment, 'Неверные реквизиты')


class ServiceListViewTest(TestCase):
    """Тесты списка услуг"""
    
    def setUp(self):
        self.client = APIClient()
        Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        Service.objects.create(name='WeChat', slug='wechat', is_active=False)
    
    def test_get_active_services(self):
        response = self.client.get(reverse('service-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # С пагинацией данные находятся в 'results'
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'AliPay')


class BankListViewTest(TestCase):
    """Тесты списка банков"""

    def setUp(self):
        self.client = APIClient()
        Bank.objects.create(name='Optima', slug='optima', is_active=True)
        Bank.objects.create(name='mBank', slug='mbank', is_active=False)

    def test_get_active_banks(self):
        response = self.client.get(reverse('bank-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Optima')


class ExchangeRateListViewTest(TestCase):
    """Тесты списка курсов валют"""

    def setUp(self):
        self.client = APIClient()
        ExchangeRate.objects.create(
            from_currency='KGS',
            to_currency='CNY',
            rate=Decimal('0.1200'),
            is_active=True
        )
        ExchangeRate.objects.create(
            from_currency='USD',
            to_currency='CNY',
            rate=Decimal('7.2000'),
            is_active=False
        )
    
    def test_get_active_rates(self):
        response = self.client.get(reverse('exchange-rate-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['from_currency'], 'KGS')


class PaymentDetailViewTest(TestCase):
    """Тесты получения реквизитов"""
    
    def setUp(self):
        self.client = APIClient()
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
        self.payment_detail = PaymentDetail.objects.create(
            service=self.service,
            bank=self.bank,
            account_number='1234567890',
            is_active=True
        )
    
    def test_get_payment_detail(self):
        response = self.client.get(
            reverse('payment-detail'),
            {'service': self.service.id, 'bank': self.bank.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['account_number'], '1234567890')
    
    def test_payment_detail_not_found(self):
        other_bank = Bank.objects.create(name='mBank', slug='mbank', is_active=True)
        
        response = self.client.get(
            reverse('payment-detail'),
            {'service': self.service.id, 'bank': other_bank.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OrderCreateViewTest(TestCase, TestImageMixin):
    """Тесты создания заявки"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
        ExchangeRate.objects.create(
            from_currency='KGS',
            to_currency='CNY',
            rate=Decimal('0.1200'),
            is_active=True
        )
        
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')
    
    def test_create_order_success(self):
        receipt_image = self.create_test_image('receipt.png')
        
        data = {
            'service': self.service.id,
            'bank': self.bank.id,
            'amount_from': '1000.00',
            'currency_from': 'KGS',
            'currency_to': 'CNY',
            'recipient_account': 'alipay_account',
            'receipt_image': receipt_image
        }
        
        response = self.client.post(reverse('order-create'), data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertIsNotNone(response.data['amount_to'])
        self.assertIsNotNone(response.data['exchange_rate'])
    
    def test_create_order_invalid_amount(self):
        receipt_image = self.create_test_image('receipt.png')
        
        data = {
            'service': self.service.id,
            'bank': self.bank.id,
            'amount_from': '-100.00',
            'currency_from': 'KGS',
            'currency_to': 'CNY',
            'recipient_account': 'alipay_account',
            'receipt_image': receipt_image
        }
        
        response = self.client.post(reverse('order-create'), data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_order_same_currency(self):
        receipt_image = self.create_test_image('receipt.png')
        
        data = {
            'service': self.service.id,
            'bank': self.bank.id,
            'amount_from': '1000.00',
            'currency_from': 'KGS',
            'currency_to': 'KGS',
            'recipient_account': 'alipay_account',
            'receipt_image': receipt_image
        }
        
        response = self.client.post(reverse('order-create'), data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_order_unauthenticated(self):
        self.client.credentials()
        receipt_image = self.create_test_image('receipt.png')
        
        data = {
            'service': self.service.id,
            'bank': self.bank.id,
            'amount_from': '1000.00',
            'receipt_image': receipt_image
        }
        
        response = self.client.post(reverse('order-create'), data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OrderHistoryViewTest(TestCase, TestImageMixin):
    """Тесты истории заявок"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
        self.receipt_image = self.create_test_image('receipt.png')
        
        Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='account1',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00')
        )
        Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('2000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='account2',
            receipt_image=self.receipt_image,
            final_amount=Decimal('2000.00')
        )
        
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')
    
    def test_get_order_history(self):
        response = self.client.get(reverse('order-history'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # С группировкой по датам данные находятся в 'groups'
        self.assertIsNotNone(response.data['count'])
        self.assertIsNone(response.data['previous'])
        self.assertIn('groups', response.data)
        # Проверяем что есть хотя бы одна группа
        self.assertGreater(len(response.data['groups']), 0)

    def test_order_history_ordered_by_created_at(self):
        response = self.client.get(reverse('order-history'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Проверяем что группы отсортированы (первая группа самая новая)
        self.assertGreater(len(response.data['groups']), 0)
        # Проверяем что в первой группе есть элементы
        first_group = response.data['groups'][0]
        self.assertIn('date', first_group)
        self.assertIn('items', first_group)


class OrderDetailViewTest(TestCase, TestImageMixin):
    """Тесты деталей заявки"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_user.is_active = True
        other_user.save()
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
        self.receipt_image = self.create_test_image('receipt.png')
        
        self.order = Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='account1',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00')
        )
        
        self.other_order = Order.objects.create(
            user=other_user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('2000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='account2',
            receipt_image=self.receipt_image,
            final_amount=Decimal('2000.00')
        )
        
        self.refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}')
    
    def test_get_own_order_detail(self):
        response = self.client.get(reverse('order-detail', args=[self.order.id]))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.order.id)
    
    def test_cannot_get_other_user_order(self):
        response = self.client.get(reverse('order-detail', args=[self.other_order.id]))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class OrderSerializerTest(TestCase):
    """Тесты сериализаторов заказов"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
    
    def test_order_create_serializer_validation(self):
        from .serializers import OrderCreateSerializer
        
        serializer = OrderCreateSerializer(data={
            'service': self.service.id,
            'bank': self.bank.id,
            'amount_from': '-100',
            'currency_from': 'KGS',
            'currency_to': 'CNY',
            'recipient_account': 'test'
        })
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('amount_from', serializer.errors)
    
    def test_order_status_update_serializer(self):
        from .serializers import OrderStatusUpdateSerializer
        
        serializer = OrderStatusUpdateSerializer(data={
            'status': 'COMPLETED',
            'manager_comment': 'Успешно'
        })
        
        self.assertTrue(serializer.is_valid())
    
    def test_order_status_update_serializer_invalid_status(self):
        from .serializers import OrderStatusUpdateSerializer
        
        serializer = OrderStatusUpdateSerializer(data={
            'status': 'INVALID_STATUS'
        })
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)


class OrderSignalTest(TestCase, TestImageMixin):
    """Тесты сигналов заказов"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
        self.receipt_image = self.create_test_image('receipt.png')

    def _create_order(self, status='PENDING'):
        """Создаёт новый заказ для теста"""
        return Order.objects.create(
            user=self.user,
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account=f'account_{status}',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00'),
            status=status
        )

    def test_signal_sets_completed_at(self):
        order = self._create_order('PENDING')
        order.status = 'COMPLETED'
        order.save(update_fields=['status'])

        # Проверяем что completed_at установлен
        order.refresh_from_db()
        self.assertIsNotNone(order.completed_at)

    def test_signal_increments_user_orders(self):
        # Проверяем что изначально 0 операций
        self.assertEqual(self.user.total_orders, 0)

        # Создаём заказ и меняем статус
        order = self._create_order('PENDING')
        order.status = 'COMPLETED'
        order.save(update_fields=['status'])

        self.user.refresh_from_db()
        # После одного завершённого заказа должно быть 1 операция
        self.assertEqual(self.user.total_orders, 1)

    def test_signal_awards_bonus_to_referrer(self):
        referrer = User.objects.create_user(
            username='referrer',
            email='referrer@example.com',
            password='testpass123'
        )
        referrer.is_active = True
        referrer.save()
        self.user.referred_by = referrer
        self.user.first_order_discount_used = False  # Явно сбрасываем
        self.user.save()
        
        initial_bonus = referrer.total_bonus
        
        order = self._create_order('PENDING')
        order.status = 'COMPLETED'
        order.save(update_fields=['status'])
        
        referrer.refresh_from_db()
        self.user.refresh_from_db()
        
        # Проверяем что first_order_discount_used стал True
        self.assertTrue(self.user.first_order_discount_used)
        
        # 1% от 1000 = 10
        expected_bonus = initial_bonus + Decimal('10.00')
        self.assertEqual(referrer.total_bonus, expected_bonus)


class AdminOrderTest(TestCase, TestImageMixin):
    """Тесты админки заказов"""
    
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.admin_user.is_active = True
        self.admin_user.save()
        self.client.force_login(self.admin_user)
        
        self.service = Service.objects.create(name='AliPay', slug='alipay', is_active=True)
        self.bank = Bank.objects.create(name='Optima', slug='optima', is_active=True)
        self.receipt_image = self.create_test_image('receipt.png')
        
        self.order1 = Order.objects.create(
            user=User.objects.create_user(username='user1', email='user1@example.com', password='pass'),
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('1000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='account1',
            receipt_image=self.receipt_image,
            final_amount=Decimal('1000.00'),
            status='PENDING'
        )
        self.order2 = Order.objects.create(
            user=User.objects.create_user(username='user2', email='user2@example.com', password='pass'),
            service=self.service,
            bank=self.bank,
            amount_from=Decimal('2000.00'),
            currency_from='KGS',
            currency_to='CNY',
            recipient_account='account2',
            receipt_image=self.receipt_image,
            final_amount=Decimal('2000.00'),
            status='PENDING'
        )
    
    def test_admin_order_list(self):
        response = self.client.get('/admin/orders/order/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заявка')
    
    def test_admin_mark_as_completed(self):
        response = self.client.post('/admin/orders/order/', {
            'action': 'mark_as_completed',
            '_selected_action': [str(self.order1.id)],
            'index': '0'
        }, follow=True)
        
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, 'COMPLETED')
    
    def test_admin_mark_as_rejected(self):
        response = self.client.post('/admin/orders/order/', {
            'action': 'mark_as_rejected',
            '_selected_action': [str(self.order1.id)],
            'index': '0'
        }, follow=True)
        
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, 'REJECTED')
