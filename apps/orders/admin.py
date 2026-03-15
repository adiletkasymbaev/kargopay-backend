from django.contrib import admin
from .models import Service, Bank, PaymentDetail, ExchangeRate, Order

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(PaymentDetail)
class PaymentDetailAdmin(admin.ModelAdmin):
    list_display = ('service', 'bank', 'account_number', 'is_active', 'updated_at')
    list_filter = ('is_active', 'service', 'bank')
    search_fields = ('account_number', 'recipient_name')


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('from_currency', 'to_currency', 'rate', 'is_active', 'updated_at')
    list_filter = ('is_active', 'from_currency', 'to_currency')
    list_editable = ('rate', 'is_active')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'service', 'bank', 'amount_from',
        'amount_to', 'status', 'created_at', 'completed_at'
    )
    list_filter = ('status', 'service', 'bank', 'created_at')
    search_fields = ('user__email', 'recipient_account', 'id')
    date_hierarchy = 'created_at'

    # Поля, доступные для редактирования при создании
    fieldsets = (
        ('Клиент и услуга', {
            'fields': ('user', 'service', 'bank', 'recipient_account')
        }),
        ('Суммы', {
            'fields': ('amount_from', 'currency_from', 'currency_to')
        }),
        ('Чек', {
            'fields': ('receipt_image',)
        }),
        ('Статус', {
            'fields': ('status', 'manager_comment')
        }),
        ('Автоматические данные', {
            'fields': (
                'amount_to', 'exchange_rate', 
                'discount_percent', 'discount_amount', 'final_amount',
                'created_at', 'updated_at', 'completed_at'
            ),
            'classes': ('collapse',),  # Скрыть под кат
            'description': 'Эти поля заполняются автоматически'
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """
        Делает поля доступными только при создании.
        Если obj существует (редактирование) — поля становятся readonly.
        """
        if obj:  # Режим редактирования
            return (
                'user', 'service', 'bank', 'amount_from', 'currency_from',
                'currency_to', 'recipient_account', 'receipt_image',
                'amount_to', 'exchange_rate', 'discount_percent', 
                'discount_amount', 'final_amount',
                'created_at', 'updated_at', 'completed_at'
            )
        else:  # Режим создания
            return (
                'amount_to', 'exchange_rate', 'discount_percent', 
                'discount_amount', 'final_amount',
                'created_at', 'updated_at', 'completed_at'
            )

    def save_model(self, request, obj, form, change):
        """Автоматический расчёт сумм при сохранении"""
        if not change:  # Только при создании
            obj.calculate_amounts()
        super().save_model(request, obj, form, change)

    actions = ['mark_as_completed', 'mark_as_rejected']

    def mark_as_completed(self, request, queryset):
        queryset.update(status='COMPLETED')
    mark_as_completed.short_description = "✅ Отметить как выполненные"

    def mark_as_rejected(self, request, queryset):
        queryset.update(status='REJECTED')
    mark_as_rejected.short_description = "❌ Отметить как отклонённые"