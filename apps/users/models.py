from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
import secrets
import random

class CustomUserManager(UserManager):
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('username', email)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email=email, password=password, **extra_fields)

class User(AbstractUser):
    # Служебное поле для совместимости
    username = models.CharField(
        max_length=255, 
        unique=True, 
        editable=False, 
        blank=True, 
        null=True,
        verbose_name=_('Логин (служебное поле)')
    )
    
    # Основное поле для входа
    email = models.EmailField(
        unique=True,
        verbose_name=_('Электронная почта')
    )
    
    # Дополнительные поля
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name=_('Номер телефона')
    )
    
    pin_code = models.CharField(
        max_length=4, 
        blank=True, 
        null=True, 
        help_text=_("4-значный пин-код для быстрых операций"),
        verbose_name=_('PIN-код')
    )
    
    # Реферальная система
    referral_code = models.CharField(
        max_length=10, 
        unique=True, 
        blank=True,
        verbose_name=_('Реферальный код')
    )
    
    referred_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='referred_users',
        verbose_name=_('Пригласивший пользователь')
    )
    
    # Статистика и бонусы
    total_orders = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Всего операций')
    )
    
    total_bonus = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name=_('Накопленные бонусы (сом)')
    )
    
    first_order_discount_used = models.BooleanField(
        default=False,
        verbose_name=_('Скидка новичка использована')
    )
    
    # AliPay QR код
    alipay_qr_code = models.ImageField(
        upload_to='users/alipay_qr/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name=_('QR-код AliPay'),
        help_text=_('QR-код кошелька AliPay пользователя')
    )

    # Настройки аутентификации
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        if not self.referral_code:
            self.referral_code = secrets.token_urlsafe(6).upper()
        # Устанавливаем is_active=False только для обычных пользователей (не суперпользователей)
        if not self.pk and not self.is_superuser:
            self.is_active = False
        super().save(*args, **kwargs)

    def get_discount_level(self):
        """Возвращает текущий уровень скидки и процент"""
        if self.total_orders >= 10:
            return {'level': 'Gold', 'discount': 0.002}  # 0.002% = 0.00002
        elif self.total_orders >= 5:
            return {'level': 'Silver', 'discount': 0.001}  # 0.001% = 0.00001
        else:
            return {'level': 'Bronze', 'discount': 0.0005}  # 0.0005% = 0.000005

    def get_first_order_discount(self):
        """Скидка для нового пользователя по рефералке"""
        if self.referred_by and not self.first_order_discount_used:
            return 0.005  # 0.005% = 0.00005
        return 0.0

    def increment_orders(self):
        """Увеличивает счетчик операций и обновляет статус"""
        self.total_orders += 1
        if self.referred_by and not self.first_order_discount_used:
            self.first_order_discount_used = True
        self.save()

    class Meta:
        verbose_name = _('Пользователь')
        verbose_name_plural = _('Пользователи')

    def __str__(self):
        return self.email
    
class EmailVerificationCode(models.Model):
    """Коды подтверждения email"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Код подтверждения email'
        verbose_name_plural = 'Коды подтверждения email'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.code}"
    
    @classmethod
    def generate_code(cls):
        """Генерация 6-значного кода"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    @classmethod
    def create_for_user(cls, user):
        """Создать новый код для пользователя"""
        # Деактивируем старые неиспользованные коды
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        
        code = cls.objects.create(
            user=user,
            code=cls.generate_code(),
            expires_at=timezone.now() + timedelta(minutes=15)  # 15 минут
        )
        return code
    
    def is_valid(self):
        """Проверка валидности кода"""
        return not self.is_used and timezone.now() < self.expires_at