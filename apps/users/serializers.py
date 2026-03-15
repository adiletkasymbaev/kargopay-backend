from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .models import EmailVerificationCode, User
from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        user = authenticate(username=email, password=password)

        if not user:
            raise serializers.ValidationError('Неверный email или пароль')

        if not user.is_active:
            raise serializers.ValidationError('Аккаунт не активирован. Подтвердите email.')

        data['user'] = user
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError('Пользователь с таким email не найден')
        return value

    def save(self, **kwargs):
        email = self.validated_data['email']
        user = User.objects.get(email=email)

        verification = EmailVerificationCode.create_for_user(user)
        send_mail(
            subject='🔐 KargoPay: Сброс пароля',
            message=f'Ваш код для сброса пароля: {verification.code}\n\nКод действителен 15 минут.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return verification


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)
    new_password_confirm = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError('Пароли не совпадают')

        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            raise serializers.ValidationError('Пользователь не найден')

        verification = EmailVerificationCode.objects.filter(
            user=user,
            code=data['code'],
            is_used=False
        ).first()

        if not verification:
            raise serializers.ValidationError('Неверный код')

        if not verification.is_valid():
            raise serializers.ValidationError('Код истёк')

        data['user'] = user
        data['verification'] = verification
        return data

    def save(self, **kwargs):
        user = self.validated_data['user']
        verification = self.validated_data['verification']

        user.set_password(self.validated_data['new_password'])
        user.save()

        verification.is_used = True
        verification.save()

        return user


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Неверный пароль')
        return value

class CustomRegisterSerializer(RegisterSerializer):
    username = serializers.CharField(required=False, allow_blank=True, default='')
    password1 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password2 = serializers.CharField(write_only=True, required=False, allow_blank=True)
    referral_code = serializers.CharField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)

    def validate_username(self, username):
        # Игнорируем username, возвращаем пустую строку
        return ''

    def validate_email(self, value):
        user = User.objects.filter(email=value).first()
        if user:
            if user.is_active:
                raise serializers.ValidationError("Пользователь с таким email уже существует")
            verification = EmailVerificationCode.create_for_user(user)
            send_mail(
                subject='🔐 KargoPay: Код подтверждения',
                message=f'Ваш код подтверждения: {verification.code}\n\nКод действителен 15 минут.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            raise serializers.ValidationError("__unverified__")
        return value

    def validate_referral_code(self, value):
        if value and not User.objects.filter(referral_code=value).exists():
            raise serializers.ValidationError("Неверный реферальный код")
        return value

    def validate(self, data):
        # Пропускаем валидацию паролей из родительского класса
        if data.get('password1') and data.get('password2') and data['password1'] != data['password2']:
            raise serializers.ValidationError(_("The two password fields didn't match."))
        return data

    def get_cleaned_data(self):
        return {
            'username': '',
            'email': self.validated_data.get('email', ''),
            'password1': self.validated_data.get('password1', ''),
            'password2': self.validated_data.get('password2', ''),
            'referral_code': self.validated_data.get('referral_code', ''),
            'first_name': self.validated_data.get('first_name', ''),
            'last_name': self.validated_data.get('last_name', ''),
        }

    def save(self, request):
        adapter = get_adapter()
        user = adapter.new_user(request)
        self.cleaned_data = self.get_cleaned_data()

        if self.cleaned_data.get("email"):
            user.email = self.cleaned_data["email"]

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        if self.cleaned_data.get("referral_code"):
            referrer = User.objects.filter(referral_code=self.cleaned_data['referral_code']).first()
            if referrer:
                user.referred_by = referrer

        user.set_password(self.cleaned_data["password1"])
        user.save()

        # Создаём запись EmailAddress для allauth (но не отправляем email)
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=False,
            primary=True
        )

        verification = EmailVerificationCode.create_for_user(user)
        send_mail(
            subject='🔐 KargoPay: Код подтверждения',
            message=f'Ваш код подтверждения: {verification.code}\n\nКод действителен 15 минут.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return user

class UserSerializer(serializers.ModelSerializer):
    discount_level = serializers.SerializerMethodField()
    first_order_discount = serializers.SerializerMethodField()
    referred_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'referral_code',
            'total_orders', 'total_bonus', 'discount_level',
            'first_order_discount', 'referred_count'
        )
        read_only_fields = ('id', 'email', 'referral_code', 'total_orders', 'total_bonus')

    def get_discount_level(self, obj):
        return obj.get_discount_level()

    def get_first_order_discount(self, obj):
        return obj.get_first_order_discount()

    def get_referred_count(self, obj):
        return obj.referred_users.count()
    
    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_discount_level(self, obj):
        return obj.get_discount_level()

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_first_order_discount(self, obj):
        return obj.get_first_order_discount()

    @extend_schema_field(OpenApiTypes.INT)
    def get_referred_count(self, obj):
        return obj.referred_users.count()


class ReferralCodeApplySerializer(serializers.Serializer):
    referral_code = serializers.CharField(max_length=10, required=True)

class ReferralStatsSerializer(serializers.ModelSerializer):
    discount_level = serializers.SerializerMethodField()
    referred_count = serializers.SerializerMethodField()
    referral_link = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'referral_code', 'referral_link', 'referred_count', 
            'total_bonus', 'discount_level', 'total_orders'
        )

    def get_discount_level(self, obj):
        return obj.get_discount_level()

    def get_referred_count(self, obj):
        return obj.referred_users.count()

    def get_referral_link(self, obj):
        return f"https://kargopay.kg/ref/{obj.referral_code}"
    
    @extend_schema_field(OpenApiTypes.STR)
    def get_referral_link(self, obj):
        return f"https://kargopay.app/ref/{obj.referral_code}"

    @extend_schema_field(OpenApiTypes.INT)
    def get_referred_count(self, obj):
        return obj.referred_users.count()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_discount_level(self, obj):
        return obj.get_discount_level()
    
class RequestVerificationCodeSerializer(serializers.Serializer):
    """Запрос кода подтверждения"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Пользователь с таким email не найден")
        
        if user.is_active:
            raise serializers.ValidationError("Email уже подтверждён")
        
        return value
    
    def save(self, **kwargs):
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        
        # Создаём код
        verification = EmailVerificationCode.create_for_user(user)
        
        # Отправляем email
        send_mail(
            subject='🔐 KargoPay: Код подтверждения',
            message=f'Ваш код подтверждения: {verification.code}\n\nКод действителен 15 минут.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        return verification


class VerifyEmailSerializer(serializers.Serializer):
    """Подтверждение кода"""
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    
    def validate(self, data):
        email = data.get('email')
        code = data.get('code')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Пользователь не найден")
        
        verification = EmailVerificationCode.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).first()
        
        if not verification:
            raise serializers.ValidationError("Неверный код")
        
        if not verification.is_valid():
            raise serializers.ValidationError("Код истёк или уже использован")
        
        return data
    
    def save(self, **kwargs):
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        
        # Активируем пользователя
        user.is_active = True
        user.save()
        
        # Помечаем код как использованный
        verification = EmailVerificationCode.objects.get(
            user=user,
            code=self.validated_data['code']
        )
        verification.is_used = True
        verification.save()
        
        # Создаём уведомление "Добро пожаловать"
        from apps.notifications.models import Notification
        Notification.objects.create(
            user=user,
            title='🎉 Добро пожаловать в KargoPay!',
            message='Ваш аккаунт успешно активирован. Теперь вы можете создавать заявки на пополнение.',
            notification_type='WELCOME',
        )
        
        return user