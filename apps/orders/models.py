from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.users.models import User
from decimal import Decimal


class Service(models.Model):
    """Услуги (например, пополнение AliPay, WeChat и т.д.)"""
    name = models.CharField(
        max_length=100,
        verbose_name=_('Название услуги')
    )
    slug = models.SlugField(
        unique=True,
        verbose_name=_('URL-слаг')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Описание')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Активна')
    )
    icon = models.ImageField(
        upload_to='services/icons/',
        blank=True,
        null=True,
        verbose_name=_('Иконка')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )

    class Meta:
        verbose_name = _('Услуга')
        verbose_name_plural = _('Услуги')
        ordering = ['name']

    def __str__(self):
        return self.name


class Bank(models.Model):
    """Банки для оплаты (mBank, Optima и т.д.)"""
    name = models.CharField(
        max_length=100,
        verbose_name=_('Название банка')
    )
    slug = models.SlugField(
        unique=True,
        verbose_name=_('URL-слаг')
    )
    logo = models.ImageField(
        upload_to='banks/logos/',
        blank=True,
        null=True,
        verbose_name=_('Логотип')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Активен')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )

    class Meta:
        verbose_name = _('Банк')
        verbose_name_plural = _('Банки')
        ordering = ['name']

    def __str__(self):
        return self.name


class PaymentDetail(models.Model):
    """Реквизиты для каждой пары Услуга + Банк"""
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='payment_details',
        verbose_name=_('Услуга')
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.CASCADE,
        related_name='payment_details',
        verbose_name=_('Банк')
    )
    
    # Реквизиты
    account_number = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Номер счёта/карты'),
        help_text=_('Номер счёта или карты для оплаты')
    )
    qr_code = models.ImageField(
        upload_to='payment/qr/',
        blank=True,
        null=True,
        verbose_name=_('QR-код для оплаты'),
        help_text=_('QR-код для быстрой оплаты')
    )
    recipient_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Получатель'),
        help_text=_('ФИО получателя платежа')
    )
    additional_info = models.TextField(
        blank=True,
        verbose_name=_('Дополнительная информация'),
        help_text=_('Дополнительная информация для клиента')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Активен')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Дата обновления')
    )

    class Meta:
        verbose_name = _('Платёжные реквизиты')
        verbose_name_plural = _('Платёжные реквизиты')
        unique_together = ['service', 'bank']

    def __str__(self):
        return f"{self.service.name} - {self.bank.name}"


class ExchangeRate(models.Model):
    """Курсы валют"""
    CURRENCY_CHOICES = (
        ('KGS', _('KGS - Киргизский сом')),
        ('RUB', _('RUB - Российский рубль')),
        ('USD', _('USD - Доллар США')),
        ('CNY', _('CNY - Китайский юань')),
    )
    
    from_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        verbose_name=_('Валюта отдачи')
    )
    to_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        verbose_name=_('Валюта получения')
    )
    rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Курс обмена'),
        help_text=_('Курс обмена валют')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Активен')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Дата обновления')
    )

    class Meta:
        verbose_name = _('Курс валют')
        verbose_name_plural = _('Курсы валют')
        unique_together = ['from_currency', 'to_currency']

    def __str__(self):
        return f"{self.from_currency} → {self.to_currency}: {self.rate}"


class Order(models.Model):
    """Заявка на пополнение"""
    STATUS_CHOICES = (
        ('PENDING', _('На проверке')),
        ('COMPLETED', _('Выполнено')),
        ('REJECTED', _('Отклонено')),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name=_('Пользователь')
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name=_('Услуга')
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name=_('Банк')
    )
    
    # Суммы и валюты
    amount_from = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Сумма к оплате'),
        help_text=_('Сумма к оплате (KGS)')
    )
    currency_from = models.CharField(
        max_length=3,
        default='KGS',
        verbose_name=_('Валюта оплаты')
    )
    amount_to = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Сумма зачисления'),
        help_text=_('Сумма зачисления (CNY)')
    )
    currency_to = models.CharField(
        max_length=3,
        default='CNY',
        verbose_name=_('Валюта зачисления')
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name=_('Применённый курс'),
        help_text=_('Курс обмена, применённый к операции')
    )
    
    # Реквизиты получения
    recipient_account = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Счёт получателя'),
        help_text=_('Кошелёк/телефон получателя (AliPay). Если не указан, используется QR-код из профиля')
    )
    
    # Чек об оплате
    receipt_image = models.ImageField(
        upload_to='receipts/%Y/%m/%d/',
        verbose_name=_('Чек об оплате'),
        help_text=_('Скриншот чека об оплате')
    )

    recipient_qr_code = models.ImageField(
        upload_to='receipts/qr/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name=_('QR-код получателя'),
        help_text=_('QR-код кошелька/счёта получателя')
    )
    
    # Статусы
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name=_('Статус')
    )
    manager_comment = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Комментарий менеджера'),
        help_text=_('Комментарий менеджера (при отклонении)')
    )
    
    # Скидки и бонусы
    discount_percent = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        verbose_name=_('Скидка %'),
        help_text=_('Применённая скидка в процентах')
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('Сумма скидки'),
        help_text=_('Сумма скидки в валюте получения')
    )
    final_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Итоговая сумма к оплате'),
        help_text=_('Итоговая сумма после всех расчётов')
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Дата обновления')
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Дата выполнения')
    )

    class Meta:
        verbose_name = _('Заявка')
        verbose_name_plural = _('Заявки')
        ordering = ['-created_at']

    def __str__(self):
        return f"Заявка #{self.id} - {self.user.email} - {self.status}"

    def calculate_amounts(self):
        """Расчёт сумм с учётом курса (без скидки - скидка рассчитывается на фронтенде)"""
        # 1. Получаем курс (самый свежий активный)
        rate_obj = ExchangeRate.objects.filter(
            from_currency=self.currency_from,
            to_currency=self.currency_to,
            is_active=True
        ).order_by('-updated_at').first()

        if rate_obj:
            self.exchange_rate = rate_obj.rate
        else:
            self.exchange_rate = Decimal('1.0')

        # 2. Базовая сумма зачисления (без учёта скидки)
        self.amount_to = self.amount_from * self.exchange_rate
        self.final_amount = self.amount_from
        # discount_percent и discount_amount остаются 0 (установлены по умолчанию)

    def save(self, *args, **kwargs):
        # Расчёт сумм только при создании нового объекта
        if not self.pk:
            self.calculate_amounts()
        super().save(*args, **kwargs)

    def mark_as_completed(self):
        """Метод для отметки заказа как выполненного"""
        from django.utils import timezone
        self.status = 'COMPLETED'
        if not self.completed_at:
            self.completed_at = timezone.now()
        self.save()

    def mark_as_rejected(self, comment=''):
        """Метод для отметки заказа как отклонённого"""
        self.status = 'REJECTED'
        self.manager_comment = comment
        self.save()