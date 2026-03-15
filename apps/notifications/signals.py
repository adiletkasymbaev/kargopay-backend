from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from apps.orders.models import Order
from apps.notifications.models import Notification, PushToken
from decimal import Decimal


@receiver(post_save, sender=Order)
def order_status_changed(sender, instance, created, update_fields, **kwargs):
    """
    Создаёт уведомление при изменении статуса заявки
    Бонусы и счётчики обрабатываются в orders/signals.py
    """
    # Проверяем статус напрямую (без update_fields)
    if instance.status not in ['COMPLETED', 'REJECTED']:
        return

    # Обновляем completed_at для COMPLETED (если ещё не обновлён)
    # Это дублирование на случай если orders/signals.py не подключён
    if instance.status == 'COMPLETED' and not instance.completed_at:
        instance.completed_at = timezone.now()
        Order.objects.filter(pk=instance.pk).update(completed_at=instance.completed_at)

    user = instance.user

    # === Уведомления ===
    notification_data = {
        'COMPLETED': {
            'type': 'ORDER_COMPLETED',
            'title': '✅ Заявка выполнена',
            'message': f'Ваша заявка #{instance.id} выполнена. Средства зачислены на AliPay.',
        },
        'REJECTED': {
            'type': 'ORDER_REJECTED',
            'title': '❌ Заявка отклонена',
            'message': f'Ваша заявка #{instance.id} отклонена. Причина: {instance.manager_comment or "Не указана"}',
        },
    }

    data = notification_data.get(instance.status)
    if not data:
        return

    # Проверка на дубликаты уведомлений
    existing = Notification.objects.filter(
        user=user,
        related_object_id=instance.id,
        related_object_type='Order',
        notification_type=data['type']
    ).first()

    if existing:
        return

    # Создаём уведомление
    notification = Notification.objects.create(
        user=user,
        title=data['title'],
        message=data['message'],
        notification_type=data['type'],
        related_object_id=instance.id,
        related_object_type='Order',
    )

    # Отправка Push
    tokens = PushToken.objects.filter(user=user, is_active=True).values_list('token', flat=True)
    if tokens:
        from apps.notifications.firebase import send_bulk_push_notification
        result = send_bulk_push_notification(
            tokens=list(tokens),
            title=data['title'],
            body=data['message'],
            data={
                'type': data['type'],
                'order_id': str(instance.id),
                'notification_id': str(notification.id),
            }
        )
        if result.get('success', 0) > 0:
            notification.is_sent = True
            notification.sent_at = timezone.now()
            notification.save()