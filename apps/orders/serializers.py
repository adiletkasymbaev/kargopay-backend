from rest_framework import serializers
from .models import Service, Bank, PaymentDetail, ExchangeRate, Order
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from .utils import decode_base64_file

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ('id', 'name', 'slug', 'description', 'icon', 'is_active')


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bank
        fields = ('id', 'name', 'slug', 'logo', 'is_active')


class PaymentDetailSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    qr_code = serializers.SerializerMethodField()

    class Meta:
        model = PaymentDetail
        fields = (
            'id', 'service', 'bank', 'service_name', 'bank_name',
            'account_number', 'qr_code', 'recipient_name',
            'additional_info', 'is_active'
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_qr_code(self, obj):
        request = self.context.get('request')
        if obj.qr_code and request:
            return request.build_absolute_uri(obj.qr_code.url)
        return None


class PaymentDetailCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDetail
        fields = (
            'service', 'bank', 'account_number', 'qr_code',
            'recipient_name', 'additional_info', 'is_active'
        )


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ('id', 'from_currency', 'to_currency', 'rate', 'updated_at')


class ExchangeRateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ('from_currency', 'to_currency', 'rate', 'is_active')


class OrderCreateSerializer(serializers.ModelSerializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    bank = serializers.PrimaryKeyRelatedField(queryset=Bank.objects.filter(is_active=True))
    receipt_image = serializers.CharField()  # Принимает base64 строку
    recipient_qr_code = serializers.CharField(required=False, allow_blank=True)  # Принимает base64 строку

    class Meta:
        model = Order
        fields = (
            'id', 'service', 'bank', 'amount_from', 'currency_from',
            'currency_to', 'recipient_account', 'recipient_qr_code', 'receipt_image',
            'amount_to', 'exchange_rate', 'discount_percent',
            'discount_amount', 'final_amount', 'status', 'created_at'
        )
        read_only_fields = (
            'id', 'amount_to', 'exchange_rate', 'discount_percent',
            'discount_amount', 'final_amount', 'status', 'created_at'
        )

    def validate_receipt_image(self, value):
        """Проверка и декодирование base64 изображения"""
        if not value:
            raise serializers.ValidationError("Изображение чека обязательно")
        
        # Проверяем что это base64 строка
        if not value.startswith('data:image/'):
            raise serializers.ValidationError("Неверный формат изображения. Ожидается base64 строка с data:image префиксом")
        
        return value

    def validate_recipient_qr_code(self, value):
        """Проверка и декодирование base64 QR кода"""
        if not value:
            return value
        
        # Проверяем что это base64 строка
        if not value.startswith('data:image/'):
            raise serializers.ValidationError("Неверный формат QR кода. Ожидается base64 строка с data:image префиксом")
        
        return value

    def validate_amount_from(self, value):
        """Проверка положительности суммы"""
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной")
        return value

    def validate(self, data):
        """Проверка корректности валют"""
        currency_from = data.get('currency_from', 'KGS')
        currency_to = data.get('currency_to', 'CNY')
        
        # Проверка что валюты разные
        if currency_from == currency_to:
            raise serializers.ValidationError({
                'currency_from': "Валюты должны быть разными"
            })
        
        # Проверка допустимых валют
        valid_currencies = ['KGS', 'RUB', 'USD', 'CNY']
        if currency_from not in valid_currencies:
            raise serializers.ValidationError({
                'currency_from': f"Недопустимая валюта: {currency_from}"
            })
        if currency_to not in valid_currencies:
            raise serializers.ValidationError({
                'currency_to': f"Недопустимая валюта: {currency_to}"
            })
        
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        validated_data['status'] = 'PENDING'

        # Декодируем base64 изображения в файлы
        receipt_image_data = validated_data.pop('receipt_image')
        validated_data['receipt_image'] = decode_base64_file(receipt_image_data, 'receipt.png')

        recipient_qr_code_data = validated_data.get('recipient_qr_code')
        if recipient_qr_code_data:
            validated_data['recipient_qr_code'] = decode_base64_file(recipient_qr_code_data, 'recipient_qr.png')

        order = Order(**validated_data)
        order.save()  # calculate_amounts() вызывается в save()

        return order


class OrderSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    bank_name = serializers.CharField(source='bank.name', read_only=True)
    receipt_image = serializers.SerializerMethodField()
    recipient_qr_code = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'user', 'user_email', 'service', 'service_name',
            'bank', 'bank_name', 'amount_from', 'currency_from',
            'amount_to', 'currency_to', 'exchange_rate',
            'recipient_account', 'receipt_image', 'status',
            'manager_comment', 'discount_percent', 'discount_amount',
            'final_amount', 'created_at', 'updated_at', 'completed_at',
            'recipient_qr_code'
        )
        read_only_fields = (
            'id', 'user', 'user_email', 'service_name', 'bank_name',
            'amount_to', 'exchange_rate', 'discount_percent',
            'discount_amount', 'final_amount', 'status',
            'created_at', 'updated_at', 'completed_at'
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_recipient_qr_code(self, obj):
        request = self.context.get('request')
        if obj.recipient_qr_code and request:
            return request.build_absolute_uri(obj.recipient_qr_code.url)
        return None

    @extend_schema_field(OpenApiTypes.URI)
    def get_receipt_image(self, obj):
        request = self.context.get('request')
        if obj.receipt_image and request:
            return request.build_absolute_uri(obj.receipt_image.url)
        return None


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('status', 'manager_comment')

    def validate_status(self, value):
        if value not in ['PENDING', 'COMPLETED', 'REJECTED']:
            raise serializers.ValidationError("Неверный статус")
        return value

    def save(self, **kwargs):
        instance = super().save(**kwargs)
        if instance.status == 'COMPLETED' and not instance.completed_at:
            from django.utils import timezone
            instance.completed_at = timezone.now()
            instance.save()
        return instance