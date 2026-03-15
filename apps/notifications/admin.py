from django.contrib import admin
from django import forms
from django.contrib import messages
from django.shortcuts import render
from django.urls import path
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Notification, PushToken
from .utils import send_notification, send_broadcast_notification
from apps.users.models import User


class BroadcastNotificationForm(forms.Form):
    """Форма для массовой рассылки уведомлений"""
    title = forms.CharField(
        label='Заголовок',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'vTextField', 'placeholder': '🎉 Акция!'})
    )
    message = forms.CharField(
        label='Текст уведомления',
        widget=forms.Textarea(attrs={'class': 'vLargeTextField', 'rows': 4, 'placeholder': 'Текст уведомления...'})
    )
    notification_type = forms.ChoiceField(
        label='Тип уведомления',
        choices=[
            ('SYSTEM', 'Системное'),
            ('PROMO', 'Акция'),
            ('ORDER_CREATED', 'Заявка создана'),
            ('ORDER_COMPLETED', 'Заявка выполнена'),
            ('ORDER_REJECTED', 'Заявка отклонена'),
            ('BONUS_RECEIVED', 'Бонус получен'),
        ],
        widget=forms.Select(attrs={'class': 'vSelectField'})
    )
    send_to_all = forms.BooleanField(
        label='Отправить всем пользователям',
        required=False,
        help_text='Если отмечено, уведомление получат все пользователи с активными push-токенами'
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'notification_type', 'is_read', 'is_sent', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_sent', 'created_at')
    search_fields = ('user__email', 'title', 'message')
    readonly_fields = ('user', 'title', 'message', 'notification_type', 'related_object_id',
                       'related_object_type', 'created_at', 'sent_at')
    date_hierarchy = 'created_at'
    actions = ['mark_as_sent', 'mark_as_read']
    change_list_template = 'admin/notifications/notification/change_list.html'

    def has_add_permission(self, request):
        return False  # Уведомления создаются автоматически

    def has_change_permission(self, request, obj=None):
        return False  # Только просмотр

    def mark_as_sent(self, request, queryset):
        queryset.update(is_sent=True)
    mark_as_sent.short_description = "Отметить как отправленные"

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Отметить как прочитанные"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'broadcast/',
                self.admin_site.admin_view(self.broadcast_notification_view),
                name='notifications_notification_broadcast',
            ),
        ]
        return custom_urls + urls

    def broadcast_notification_view(self, request):
        """View для массовой рассылки уведомлений"""
        if request.method == 'POST':
            form = BroadcastNotificationForm(request.POST)
            if form.is_valid():
                title = form.cleaned_data['title']
                message = form.cleaned_data['message']
                notification_type = form.cleaned_data['notification_type']
                
                if form.cleaned_data.get('send_to_all'):
                    # Массовая рассылка всем пользователям
                    result = send_broadcast_notification(
                        title=title,
                        message=message,
                        notification_type=notification_type
                    )
                    self.message_user(
                        request,
                        f'Уведомление отправлено! Успешно: {result.get("success_count", 0)}, '
                        f'Неудач: {result.get("failure_count", 0)}',
                        messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        'Выберите пользователей для отправки уведомления',
                        messages.INFO
                    )
                    return HttpResponseRedirect(reverse('admin:notifications_notification_changelist'))
                
                return HttpResponseRedirect(reverse('admin:notifications_notification_changelist'))
        else:
            form = BroadcastNotificationForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Массовая рассылка уведомлений',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/notifications/notification/broadcast.html', context)


@admin.action(description='Отправить тестовое уведомление выбранным пользователям')
def send_test_notification(modeladmin, request, queryset):
    """Отправить тестовое уведомление выбранным пользователям"""
    count = 0
    for user in queryset:
        send_notification(
            user=user,
            title='🔔 Тестовое уведомление',
            message='Это тестовое уведомление из Django Admin',
            notification_type='SYSTEM'
        )
        count += 1
    
    modeladmin.message_user(
        request,
        f'Отправлено {count} тестовых уведомлений',
        messages.SUCCESS
    )


@admin.action(description='Отправить уведомление выбранным пользователям')
def send_notification_to_users(modeladmin, request, queryset):
    """Отправить уведомление выбранным пользователям"""
    # Перенаправляем на страницу с формой
    request.session['selected_user_ids'] = list(queryset.values_list('id', flat=True))
    return HttpResponseRedirect(reverse('admin:users_user_send_notification'))


@admin.register(PushToken)
class PushTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'device_type', 'is_active', 'created_at', 'last_used_at')
    list_filter = ('device_type', 'is_active', 'created_at')
    search_fields = ('user__email', 'token', 'device_info')
    readonly_fields = ('user', 'token', 'device_type', 'device_info', 'created_at', 'last_used_at')

    actions = ['deactivate_tokens', 'activate_tokens']

    def deactivate_tokens(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_tokens.short_description = "Деактивировать токены"

    def activate_tokens(self, request, queryset):
        queryset.update(is_active=True)
    activate_tokens.short_description = "Активировать токены"