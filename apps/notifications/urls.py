from django.urls import path
from .views import (
    NotificationListView,
    UnreadNotificationCountView,
    NotificationMarkAsReadView,
    NotificationMarkAllAsReadView,
    PushTokenRegisterView,
    PushTokenDeleteView,
    SendTestNotificationView,
)

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', UnreadNotificationCountView.as_view(), name='notification-unread-count'),
    path('notifications/<int:notification_id>/read/', NotificationMarkAsReadView.as_view(), name='notification-mark-read'),
    path('notifications/mark-all-read/', NotificationMarkAllAsReadView.as_view(), name='notification-mark-all-read'),
    path('push-token/register/', PushTokenRegisterView.as_view(), name='push-token-register'),
    path('push-token/delete/', PushTokenDeleteView.as_view(), name='push-token-delete'),
    path('send-test-notification/', SendTestNotificationView.as_view(), name='send-test-notification'),
]