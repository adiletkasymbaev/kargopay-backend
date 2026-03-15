from django.urls import path
from .views import (
    ServiceListView, BankListView, ExchangeRateListView,
    PaymentDetailView, OrderCreateView, OrderHistoryView,
    OrderDetailView
)

urlpatterns = [
    # Публичные endpoints
    path('services/', ServiceListView.as_view(), name='service-list'),
    path('banks/', BankListView.as_view(), name='bank-list'),
    path('rates/', ExchangeRateListView.as_view(), name='exchange-rate-list'),
    path('payment-details/', PaymentDetailView.as_view(), name='payment-detail'),
    
    # Заявки пользователя
    path('orders/', OrderCreateView.as_view(), name='order-create'),
    path('orders/history/', OrderHistoryView.as_view(), name='order-history'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
]