"""
Firebase Cloud Messaging configuration
"""
import firebase_admin
from firebase_admin import credentials, messaging
from firebase_admin.exceptions import FirebaseError, InvalidArgumentError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def initialize_firebase():
    """Инициализация Firebase приложения"""
    try:
        if not firebase_admin._apps:
            cred_path = getattr(settings, 'FIREBASE_CREDENTIALS', None)
            
            if cred_path and cred_path.exists():
                logger.info(f"Загрузка Firebase credentials из: {cred_path}")
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase инициализирован успешно")
                logger.info(f"Project ID: {firebase_admin.get_app().project_id}")
                return True
            else:
                logger.error(f"❌ Firebase credentials file not found: {cred_path}")
                return False
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Firebase: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def get_firebase_app():
    """Получить экземпляр Firebase приложения"""
    if not firebase_admin._apps:
        initialize_firebase()
    return firebase_admin.get_app() if firebase_admin._apps else None


def send_push_notification(token, title, message, data=None):
    """
    Отправка push-уведомления одному устройству

    Args:
        token: Push-токен устройства
        title: Заголовок уведомления
        message: Текст уведомления
        data: Дополнительные данные (dict)

    Returns:
        bool: True если успешно, False иначе
    """
    try:
        if not firebase_admin._apps:
            logger.warning("Firebase не инициализирован")
            if not initialize_firebase():
                return False

        logger.info(f"📤 Отправка push уведомления на токен: {token[:20]}...")
        logger.info(f"   Title: {title}")
        logger.info(f"   Body: {message}")
        logger.info(f"   Data: {data}")

        notification = messaging.Notification(
            title=title,
            body=message
        )

        message_payload = messaging.Message(
            notification=notification,
            token=token,
            data=data or {},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        content_available=True
                    )
                )
            )
        )

        response = messaging.send(message_payload)
        logger.info(f"✅ Push уведомление отправлено успешно: {response}")
        return True

    except messaging.UnregisteredError:
        logger.error(f"❌ Токен не зарегистрирован (UnregisteredError): {token}")
        logger.error("   Возможно, приложение удалено или токен устарел")
        return False
    except InvalidArgumentError as e:
        logger.error(f"❌ Неверный токен (InvalidArgumentError): {token}")
        logger.error(f"   Ошибка: {e}")
        logger.error("   Убедитесь что токен действителен и получен от FCM")
        logger.error("   Web токены должны начинаться с 'B...' или быть в формате FCMv1")
        return False
    except messaging.SenderIdMismatchError:
        logger.error(f"❌ Sender ID mismatch - проверьте google-services.json / GoogleService-Info.plist")
        return False
    except messaging.QuotaExceededError:
        logger.error("❌ Превышена квота отправки сообщений")
        return False
    except FirebaseError as e:
        logger.error(f"❌ Firebase ошибка: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки push уведомления: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def send_push_notification_multicast(tokens, title, message, data=None):
    """
    Отправка push-уведомления нескольким устройствам

    Args:
        tokens: Список push-токенов (максимум 500)
        title: Заголовок уведомления
        message: Текст уведомления
        data: Дополнительные данные (dict)

    Returns:
        dict: {
            'success_count': количество успешных отправок,
            'failure_count': количество неудач,
            'success_tokens': список успешных токенов,
            'failure_tokens': список неудачных токенов
        }
    """
    try:
        if not firebase_admin._apps:
            logger.warning("Firebase не инициализирован")
            if not initialize_firebase():
                return {
                    'success_count': 0,
                    'failure_count': len(tokens),
                    'success_tokens': [],
                    'failure_tokens': tokens
                }

        if not tokens:
            logger.warning("⚠️ Список токенов пуст")
            return {
                'success_count': 0,
                'failure_count': 0,
                'success_tokens': [],
                'failure_tokens': []
            }

        logger.info(f"📤 Multicast отправка {len(tokens)} токенам")
        logger.info(f"   Title: {title}")
        logger.info(f"   Body: {message}")
        
        # Логируем первые 3 токена для отладки
        for i, token in enumerate(tokens[:3]):
            logger.info(f"   Token {i+1}: {token[:20]}...")
        if len(tokens) > 3:
            logger.info(f"   ... и ещё {len(tokens) - 3} токенов")

        # Создаём сообщения для каждого токена
        messages = []
        for token in tokens:
            msg = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=message
                ),
                token=token,
                data=data or {},
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        click_action='FLUTTER_NOTIFICATION_CLICK'
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            content_available=True
                        )
                    )
                )
            )
            messages.append(msg)

        logger.info("🔄 Отправка multicast сообщения...")
        
        # В firebase-admin 7.x используем send_each вместо send_multicast
        response = messaging.send_each(messages)
        
        logger.info(f"📊 Результат: {response.success_count} успешно, {response.failure_count} неудач")

        success_tokens = []
        failure_tokens = []

        # Обрабатываем ответы для каждого токена
        for idx, resp in enumerate(response.responses):
            if resp.success:
                success_tokens.append(tokens[idx])
            else:
                failure_tokens.append(tokens[idx])
                logger.warning(f"   ❌ Токен {tokens[idx][:20]}... не получен: {resp.exception}")

        return {
            'success_count': response.success_count,
            'failure_count': response.failure_count,
            'success_tokens': success_tokens,
            'failure_tokens': failure_tokens
        }

    except Exception as e:
        logger.error(f"❌ Ошибка multicast отправки: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success_count': 0,
            'failure_count': len(tokens),
            'success_tokens': [],
            'failure_tokens': tokens
        }


def check_token_format(token):
    """
    Проверка формата токена
    
    Returns:
        bool: True если токен выглядит валидным
    """
    if not token:
        return False
    
    # FCMv1 токены обычно начинаются с буквы и содержат 100+ символов
    # Web токены могут быть в формате: web_TIMESTAMP_RANDOMSTRING
    if token.startswith('web_') or token.startswith('ios_') or token.startswith('android_'):
        logger.warning(f"⚠️ Токен имеет кастомный префикс: {token[:20]}...")
        # Это может быть кастомный формат - проверяем длину
        return len(token) > 50
    
    # Стандартные FCM токены
    return len(token) > 50


def send_push_by_topic(topic, title, message, data=None):
    """
    Отправка push-уведомления по теме
    
    Args:
        topic: Название темы (например, 'all_users', 'order_updates')
        title: Заголовок уведомления
        message: Текст уведомления
        data: Дополнительные данные (dict)
    
    Returns:
        messaging.SendResponse: Результат отправки
    """
    try:
        if not firebase_admin._apps:
            logger.warning("Firebase не инициализирован")
            return None
        
        notification = messaging.Notification(
            title=title,
            body=message
        )
        
        message_payload = messaging.Message(
            notification=notification,
            topic=topic,
            data=data or {}
        )
        
        response = messaging.send(message_payload)
        logger.info(f"Push по теме '{topic}' отправлен: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Ошибка отправки push по теме: {e}")
        return None


def subscribe_to_topic(tokens, topic):
    """
    Подписка устройств на тему
    
    Args:
        tokens: Список токенов
        topic: Название темы
    """
    try:
        if not firebase_admin._apps:
            return False
        
        response = messaging.subscribe_to_topic(tokens, topic)
        logger.info(f"Подписка на тему '{topic}': {response.success_count} успешно")
        return response.success_count > 0
        
    except Exception as e:
        logger.error(f"Ошибка подписки на тему: {e}")
        return False


def unsubscribe_from_topic(tokens, topic):
    """
    Отписка устройств от темы
    
    Args:
        tokens: Список токенов
        topic: Название темы
    """
    try:
        if not firebase_admin._apps:
            return False
        
        response = messaging.unsubscribe_from_topic(tokens, topic)
        logger.info(f"Отписка от темы '{topic}': {response.success_count} успешно")
        return response.success_count > 0
        
    except Exception as e:
        logger.error(f"Ошибка отписки от темы: {e}")
        return False
