from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.users.models import User


class Notification(models.Model):
    """Уведомления для пользователей"""
    
    TYPE_CHOICES = (
        ('ORDER_CREATED', _('Заявка создана')),
        ('ORDER_COMPLETED', _('Заявка выполнена')),
        ('ORDER_REJECTED', _('Заявка отклонена')),
        ('BONUS_RECEIVED', _('Бонус получен')),
        ('PROMO', _('Акция')),
        ('SYSTEM', _('Системное')),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Пользователь')
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_('Заголовок')
    )
    message = models.TextField(
        verbose_name=_('Текст уведомления')
    )
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name=_('Тип уведомления')
    )
    
    # Ссылка на связанный объект (заявку)
    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('ID связанного объекта')
    )
    related_object_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_('Тип связанного объекта')
    )
    
    # Статусы
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Прочитано')
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name=_('Push отправлен')
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Дата отправки')
    )
    
    class Meta:
        verbose_name = _('Уведомление')
        verbose_name_plural = _('Уведомления')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"


class PushToken(models.Model):
    """Push-токены устройств пользователей"""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_tokens',
        verbose_name=_('Пользователь')
    )
    token = models.CharField(
        max_length=500,
        unique=True,
        verbose_name=_('Push-токен')
    )
    device_type = models.CharField(
        max_length=20,
        default='web',
        verbose_name=_('Тип устройства'),
        help_text=_('web, ios, android')
    )
    device_info = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Информация об устройстве'),
        help_text=_('Название браузера или устройства')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Активен')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Дата создания')
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Последнее использование')
    )
    
    class Meta:
        verbose_name = _('Push-токен')
        verbose_name_plural = _('Push-токены')
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_type}"