"""
Утилиты для отправки push-уведомлений
"""
from django.utils import timezone
from apps.notifications.models import Notification, PushToken
from config.firebase import (
    send_push_notification,
    send_push_notification_multicast,
    initialize_firebase
)
import logging

logger = logging.getLogger(__name__)


def send_order_notification(user, order, notification_type):
    """
    Отправка уведомления о статусе заказа
    
    Args:
        user: Пользователь
        order: Заказ
        notification_type: Тип уведомления
    """
    titles = {
        'ORDER_CREATED': 'Заявка создана',
        'ORDER_COMPLETED': 'Заявка выполнена',
        'ORDER_REJECTED': 'Заявка отклонена',
    }
    
    messages = {
        'ORDER_CREATED': f'Ваша заявка #{order.id} принята в работу',
        'ORDER_COMPLETED': f'Ваша заявка #{order.id} выполнена',
        'ORDER_REJECTED': f'Ваша заявка #{order.id} отклонена',
    }
    
    send_notification(
        user=user,
        title=titles.get(notification_type, 'Уведомление'),
        message=messages.get(notification_type, ''),
        notification_type=notification_type,
        related_object=order
    )


def send_bonus_notification(user, bonus_amount):
    """
    Отправка уведомления о начислении бонусов
    
    Args:
        user: Пользователь
        bonus_amount: Сумма бонусов
    """
    send_notification(
        user=user,
        title='🎁 Бонус получен',
        message=f'Вам начислено {bonus_amount} бонусов',
        notification_type='BONUS_RECEIVED'
    )


def send_promo_notification(user, title, message):
    """
    Отправка промо-уведомления
    
    Args:
        user: Пользователь
        title: Заголовок акции
        message: Текст акции
    """
    send_notification(
        user=user,
        title=title,
        message=message,
        notification_type='PROMO'
    )


def send_notification(user, title, message, notification_type='SYSTEM', related_object=None):
    """
    Универсальная функция отправки уведомления
    
    Args:
        user: Пользователь
        title: Заголовок
        message: Текст
        notification_type: Тип уведомления
        related_object: Связанный объект (заказ и т.д.)
    """
    # Инициализируем Firebase
    initialize_firebase()
    
    # Создаём уведомление в базе
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        related_object_id=related_object.id if related_object else None,
        related_object_type=related_object.__class__.__name__ if related_object else None,
        is_sent=False
    )
    
    # Получаем активные токены пользователя
    tokens = list(PushToken.objects.filter(
        user=user,
        is_active=True
    ).values_list('token', flat=True))
    
    if not tokens:
        logger.warning(f"У пользователя {user.email} нет активных push-токенов")
        return notification
    
    # Отправляем push-уведомление
    try:
        if len(tokens) == 1:
            success = send_push_notification(
                token=tokens[0],
                title=title,
                message=message,
                data={
                    'type': notification_type,
                    'notification_id': str(notification.id)
                }
            )
        else:
            result = send_push_notification_multicast(
                tokens=tokens,
                title=title,
                message=message,
                data={
                    'type': notification_type,
                    'notification_id': str(notification.id)
                }
            )
            success = result['success_count'] > 0
        
        if success:
            notification.is_sent = True
            notification.sent_at = timezone.now()
            notification.save()
            logger.info(f"Push уведомление отправлено пользователю {user.email}")
        else:
            logger.warning(f"Не удалось отправить push пользователю {user.email}")
            
    except Exception as e:
        logger.error(f"Ошибка отправки push уведомления: {e}")
    
    return notification


def send_broadcast_notification(title, message, notification_type='SYSTEM', data=None):
    """
    Массовая рассылка уведомлений всем пользователям
    
    Args:
        title: Заголовок
        message: Текст
        notification_type: Тип уведомления
        data: Дополнительные данные
    
    Returns:
        dict: Результаты рассылки
    """
    initialize_firebase()
    
    # Получаем все активные токены
    active_tokens = PushToken.objects.filter(is_active=True)
    
    if not active_tokens.exists():
        return {'success_count': 0, 'failure_count': 0}
    
    # Создаём уведомления для всех пользователей
    users_notified = set()
    for push_token in active_tokens:
        if push_token.user_id not in users_notified:
            Notification.objects.create(
                user=push_token.user,
                title=title,
                message=message,
                notification_type=notification_type,
                is_sent=False
            )
            users_notified.add(push_token.user_id)
    
    # Отправляем push-уведомления
    tokens = list(active_tokens.values_list('token', flat=True))
    
    result = send_push_notification_multicast(
        tokens=tokens,
        title=title,
        message=message,
        data=data or {}
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
    
    logger.info(
        f"Массовая рассылка: {result['success_count']} успешно, "
        f"{result['failure_count']} неудач"
    )
    
    return result
