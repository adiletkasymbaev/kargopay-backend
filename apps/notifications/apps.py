from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    label = 'notifications'
    name = 'apps.notifications'

    def ready(self):
        import apps.notifications.signals