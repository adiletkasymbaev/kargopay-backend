from rest_framework import serializers
from .models import Notification, PushToken
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    related_object_url = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id', 'title', 'message', 'notification_type',
            'notification_type_display', 'related_object_id',
            'related_object_type', 'related_object_url',
            'is_read', 'is_sent', 'created_at', 'sent_at'
        )
        read_only_fields = (
            'id', 'notification_type_display', 'related_object_url',
            'is_sent', 'created_at', 'sent_at'
        )

    def get_related_object_url(self, obj):
        """Генерирует URL для связанного объекта"""
        if obj.related_object_type == 'Order':
            return f"/orders/{obj.related_object_id}/"
        return None
    
    @extend_schema_field(OpenApiTypes.STR)
    def get_related_object_url(self, obj):
        if obj.related_object_type == 'Order':
            return f"/orders/{obj.related_object_id}/"
        return None


class PushTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushToken
        fields = ('id', 'token', 'device_type', 'device_info', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')


class PushTokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=500)
    device_type = serializers.CharField(max_length=20, default='web')
    device_info = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def create(self, validated_data):
        user = self.context['request'].user
        token, created = PushToken.objects.update_or_create(
            token=validated_data['token'],
            defaults={
                'user': user,
                'device_type': validated_data.get('device_type', 'web'),
                'device_info': validated_data.get('device_info', ''),
                'is_active': True,
            }
        )
        return token