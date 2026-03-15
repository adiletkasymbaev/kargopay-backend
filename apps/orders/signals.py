from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
from .models import Order
from apps.users.models import User


@receiver(post_save, sender=Order)
def order_status_changed(sender, instance, created, update_fields, **kwargs):
    """Обработка изменения статуса заявки на COMPLETED"""
    # Обрабатываем только если статус изменился на COMPLETED
    # update_fields должен содержать 'status'
    if not update_fields or 'status' not in update_fields:
        return
    
    if instance.status != 'COMPLETED':
        return
    
    # Проверяем что completed_at ещё не установлен (чтобы не обрабатывать повторно)
    if instance.completed_at is not None:
        return
    
    # Устанавливаем completed_at без вызова другого save()
    Order.objects.filter(pk=instance.pk).update(completed_at=timezone.now())
    instance.completed_at = timezone.now()
    
    # Получаем данные о реферере ДО увеличения счётчика
    user = instance.user
    referrer = None
    bonus_amount = None
    
    if user.referred_by and not user.first_order_discount_used:
        referrer = user.referred_by
        bonus_amount = instance.amount_from * Decimal('0.01')  # 1% бонус
    
    # Увеличиваем счётчик операций пользователя (это также установит first_order_discount_used=True)
    user.increment_orders()
    
    # Начисляем бонус пригласителю
    if referrer and bonus_amount is not None:
        User.objects.filter(pk=referrer.pk).update(
            total_bonus=referrer.total_bonus + bonus_amount
        )