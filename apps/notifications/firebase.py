import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Инициализация Firebase
def initialize_firebase():
    """Инициализирует Firebase Admin SDK"""
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred, {
                'projectId': settings.FIREBASE_PROJECT_ID,
            })
    except Exception as e:
        logger.error(f"Firebase initialization error: {e}")

def send_push_notification(token, title, body, data=None):
    """
    Отправляет push-уведомление на устройство
    
    Args:
        token: Push-токен устройства
        title: Заголовок уведомления
        body: Текст уведомления
        data: Дополнительные данные (dict)
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    initialize_firebase()
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    click_action='/notifications/',
                ),
            ),
        )
        
        response = messaging.send(message)
        logger.info(f"Push sent successfully: {response}")
        return True

    except Exception as e:
        logger.error(f"Push notification error: {e}")
        return False


def send_bulk_push_notification(tokens, title, body, data=None):
    """
    Отправляет push-уведомление на несколько устройств
    
    Args:
        tokens: Список push-токенов
        title: Заголовок уведомления
        body: Текст уведомления
        data: Дополнительные данные (dict)
    
    Returns:
        dict: Статистика отправки
    """
    initialize_firebase()
    
    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=tokens,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    click_action='/notifications/',
                ),
            ),
        )
        
        response = messaging.send_each_for_multicast(message)
        
        return {
            'success': response.success_count,
            'failure': response.failure_count,
            'responses': response.responses,
        }

    except Exception as e:
        logger.error(f"Bulk push notification error: {e}")
        return {'success': 0, 'failure': len(tokens)}