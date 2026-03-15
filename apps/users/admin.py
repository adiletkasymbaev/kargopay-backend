from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
from .models import User
from apps.notifications.utils import send_notification


class ReferredUsersInline(admin.TabularInline):
    """Инлайн: список приглашённых пользователей"""
    model = User
    fields = ('email', 'referral_code', 'total_orders', 'total_bonus', 'first_order_discount_used')
    readonly_fields = ('email', 'referral_code', 'total_orders', 'total_bonus', 'first_order_discount_used')
    extra = 0
    can_delete = False
    verbose_name = _('Приглашённый пользователь')
    verbose_name_plural = _('Приглашённые пользователи')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Админ-панель пользователей с реферальной статистикой"""
    
    fieldsets = (
        (_('Основная информация'), {
            'fields': ('email', 'phone', 'pin_code', 'password')
        }),
        (_('Реферальная система'), {
            'fields': ('referral_code', 'referred_by', 'first_order_discount_used'),
            'description': _('Информация о приглашении и скидках')
        }),
        (_('Статистика'), {
            'fields': ('total_orders', 'total_bonus', 'discount_level_display'),
            'classes': ('collapse',),
            'description': _('Автоматические поля, не редактируются вручную')
        }),
        (_('Права доступа'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Даты'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone', 'password1', 'password2', 'referral_code', 'referred_by'),
        }),
    )
    
    list_display = (
        'id',
        'email_link',
        'phone',
        'referral_code',
        'referred_by_link',
        'referred_count_display',
        'total_bonus_display',
        'discount_level_badge',
        'total_orders',
        'is_active_icon',
        'date_joined',
    )
    
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'first_order_discount_used',
        ('referred_by', admin.RelatedOnlyFieldListFilter),
        ('date_joined', admin.DateFieldListFilter),
    )
    
    search_fields = ('email', 'phone', 'referral_code', 'referred_by__email')
    ordering = ('-date_joined',)
    
    readonly_fields = (
        'referral_code',
        'total_orders',
        'total_bonus',
        'first_order_discount_used',
        'discount_level_display',
        'date_joined',
        'last_login',
    )
    
    list_per_page = 25
    
    inlines = [ReferredUsersInline]
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields.pop('username', None)
        return form
    
    # === Кастомные методы (ИСПРАВЛЕНО) ===
    
    def email_link(self, obj):
        url = f'/admin/users/user/{obj.id}/change/'
        return format_html('<a href="{}">{}</a>', url, obj.email)
    email_link.short_description = _('Email')
    
    def referred_by_link(self, obj):
        if obj.referred_by:
            url = f'/admin/users/user/{obj.referred_by.id}/change/'
            return format_html('<a href="{}">{}</a>', url, obj.referred_by.email)
        return mark_safe('—')
    referred_by_link.short_description = _('Пригласил')
    
    def referred_count_display(self, obj):
        count = obj.referred_users.count()
        if count == 0:
            color = '#6c757d'
        elif count < 5:
            color = '#17a2b8'
        elif count < 10:
            color = '#ffc107'
        else:
            color = '#28a745'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>',
            color, count
        )
    referred_count_display.short_description = _('Пригласил')
    
    def total_bonus_display(self, obj):
        bonus = float(obj.total_bonus)
        if bonus == 0:
            color = '#6c757d'
        elif bonus < 100:
            color = '#17a2b8'
        elif bonus < 500:
            color = '#ffc107'
        else:
            color = '#28a745'
        return format_html(
            '<span style="color: {}; font-weight: 600;">{} сом</span>',
            color, obj.total_bonus
        )
    total_bonus_display.short_description = _('Бонусы')
    
    def discount_level_badge(self, obj):
        level = obj.get_discount_level()
        colors = {'Bronze': '#cd7f32', 'Silver': '#c0c0c0', 'Gold': '#ffd700'}
        color = colors.get(level['level'], '#6c757d')
        text_color = '#000' if level['level'] == 'Gold' else '#fff'
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 500;">{} {}%</span>',
            color, text_color, level['level'], level['discount']
        )
    discount_level_badge.short_description = _('Уровень')
    
    def discount_level_display(self, obj):
        level = obj.get_discount_level()
        return f"{level['level']} ({level['discount']}%)"
    discount_level_display.short_description = _('Текущий уровень скидки')
    
    def is_active_icon(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color: #28a745;">✓</span>')
        return mark_safe('<span style="color: #dc3545;">✗</span>')
    is_active_icon.short_description = _('Активен')
    
    # === Массовые действия ===
    actions = ['activate_users', 'deactivate_users', 'reset_first_order_discount', 'send_test_notification', 'send_notification_action']

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} пользователей активировано')
    activate_users.short_description = _('✅ Активировать пользователей')

    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} пользователей деактивировано')
    deactivate_users.short_description = _('❌ Деактивировать пользователей')

    def reset_first_order_discount(self, request, queryset):
        updated = queryset.update(first_order_discount_used=False)
        self.message_user(request, f'Скидка сброшена у {updated} пользователей')
    reset_first_order_discount.short_description = _('🔄 Сбросить скидку новичка')

    def send_test_notification(self, request, queryset):
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
        self.message_user(request, f'Отправлено {count} тестовых уведомлений')
    send_test_notification.short_description = _('🔔 Отправить тестовое уведомление')

    def send_notification_action(self, request, queryset):
        """Отправить кастомное уведомление выбранным пользователям"""
        if request.POST.get('apply'):
            # Получаем данные из POST запроса
            title = request.POST.get('notification_title', 'Уведомление')
            message = request.POST.get('notification_message', '')
            notification_type = request.POST.get('notification_type', 'SYSTEM')
            
            count = 0
            for user in queryset:
                send_notification(
                    user=user,
                    title=title,
                    message=message,
                    notification_type=notification_type
                )
                count += 1
            
            self.message_user(request, f'Отправлено {count} уведомлений')
            return None
        
        # Показываем форму для ввода данных
        from django.forms import Form, CharField, ChoiceField, Textarea, TextInput
        from django import forms
        
        class NotificationForm(Form):
            title = CharField(
                label='Заголовок',
                max_length=255,
                widget=TextInput(attrs={'class': 'vTextField'})
            )
            message = CharField(
                label='Текст',
                widget=Textarea(attrs={'class': 'vLargeTextField', 'rows': 4})
            )
            notification_type = ChoiceField(
                label='Тип',
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
        
        form = NotificationForm()
        selected_ids = ','.join(map(str, queryset.values_list('id', flat=True)))
        
        return render(request, 'admin/users/user/send_notification.html', {
            'form': form,
            'selected_ids': selected_ids,
            'title': 'Отправить уведомление',
            **self.admin_site.each_context(request)
        })
    send_notification_action.short_description = _('📩 Отправить уведомление')