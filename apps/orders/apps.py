from django.apps import AppConfig

class OrdersConfig(AppConfig):
    label = 'orders'
    name = 'apps.orders'
    verbose_name = 'Заказы и платежи'

    def ready(self):
        import apps.orders.signals