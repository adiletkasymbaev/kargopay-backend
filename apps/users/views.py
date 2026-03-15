from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import User
from .serializers import (
    LoginSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, DeleteAccountSerializer,
    CustomRegisterSerializer, ReferralCodeApplySerializer, UserSerializer,
    ReferralStatsSerializer, RequestVerificationCodeSerializer, VerifyEmailSerializer
)
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
import requests
import logging

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Auth'],
    summary='Вход',
    description='Возвращает access и refresh JWT токены',
)
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.pk,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        })


@extend_schema(
    tags=['Auth'],
    summary='Вход через Google',
    description='''Вход или регистрация через Google с использованием Firebase Authentication.

**Процесс входа:**
1. Клиент получает Firebase ID токен через Firebase SDK (Google Sign-In)
2. Токен отправляется на этот endpoint
3. Сервер верифицирует токен через Google
4. Если пользователь существует — входит в систему
5. Если пользователя нет — создаёт новый аккаунт и входит

**Тело запроса:**
- `firebase_token` (string) — Firebase ID токен, полученный после успешного Google Sign-In

**Возвращаемые данные:**
- `access` — JWT access токен
- `refresh` — JWT refresh токен
- `user` — данные пользователя:
  - `id` — ID пользователя
  - `email` — email из Google аккаунта
  - `first_name` — имя из Google аккаунта
  - `last_name` — фамилия из Google аккаунта
  - `is_new_user` — true если аккаунт был создан только что

**Пример получения токена на клиенте (Firebase SDK v9+):**
```javascript
import { GoogleAuthProvider, signInWithPopup, getAuth } from 'firebase/auth';

const provider = new GoogleAuthProvider();
const auth = getAuth();
const result = await signInWithPopup(auth, provider);
const firebaseToken = await result.user.getIdToken();

// Отправляем firebaseToken на сервер
fetch('/api/v1/auth/google/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({firebase_token: firebaseToken})
});
```''',
    request={'type': 'object', 'properties': {'firebase_token': {'type': 'string'}}},
    responses={
        200: {
            'description': 'Успешный вход через Google',
            'content': {
                'application/json': {
                    'example': {
                        'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ...',
                        'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ...',
                        'user': {
                            'id': 1,
                            'email': 'user@gmail.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'is_new_user': False
                        }
                    }
                }
            }
        },
        400: {'description': 'Неверный токен'},
        401: {'description': 'Токен не прошёл верификацию'},
    },
    examples=[
        OpenApiExample(
            'Запрос',
            value={'firebase_token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6...'},
            request_only=True
        ),
        OpenApiExample(
            'Успешный вход (существующий пользователь)',
            value={
                'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'user': {
                    'id': 1,
                    'email': 'user@gmail.com',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'is_new_user': False
                }
            },
            status_codes=[200]
        ),
        OpenApiExample(
            'Успешная регистрация (новый пользователь)',
            value={
                'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
                'user': {
                    'id': 2,
                    'email': 'newuser@gmail.com',
                    'first_name': 'Jane',
                    'last_name': 'Smith',
                    'is_new_user': True
                }
            },
            status_codes=[200]
        ),
        OpenApiExample(
            'Ошибка верификации токена',
            value={'error': 'Неверный Firebase токен'},
            status_codes=[400]
        )
    ],
)
class GoogleLoginView(APIView):
    """Вход через Google с использованием Firebase ID токена"""
    permission_classes = [permissions.AllowAny]
    serializer_class = None

    def post(self, request):
        firebase_token = request.data.get('firebase_token')
        google_id_token = request.data.get('google_id_token')

        # Если есть google_id_token - используем его (предпочтительно)
        if google_id_token:
            return self._verify_google_token(google_id_token, request)

        # Иначе пробуем использовать firebase_token
        if not firebase_token:
            return Response(
                {'error': 'Firebase токен или Google ID токен обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Пробуем верифицировать как Firebase токен
        return self._verify_firebase_token(firebase_token, request)

    def _verify_firebase_token(self, firebase_token, request):
        """Верификация Firebase ID токена"""
        try:
            # Декодируем токен для проверки
            import base64
            import json

            parts = firebase_token.split('.')
            if len(parts) == 3:
                payload = parts[1]
                padding = '=' * (4 - len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload + padding)
                token_data = json.loads(decoded_payload)

                # Если это Firebase токен (iss=securetoken.google.com), используем Firebase Admin SDK
                if 'securetoken.google.com' in token_data.get('iss', ''):
                    return self._verify_with_firebase_admin(firebase_token, request)

        except Exception:
            pass

        # Если не удалось определить тип токена, пробуем Google TokenInfo API
        return self._verify_google_token(firebase_token, request)

    def _verify_with_firebase_admin(self, firebase_token, request):
        """Верификация Firebase токена через Firebase Admin SDK"""
        try:
            from firebase_admin import auth as firebase_auth

            # Верифицируем токен через Firebase Admin SDK
            decoded_token = firebase_auth.verify_id_token(firebase_token)

            email = decoded_token.get('email')
            if not email:
                return Response(
                    {'error': 'Email не получен из токена'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Находим или создаём пользователя
            user, created = User.objects.get_or_create(email=email)

            if created:
                user.is_active = True
                user.first_name = decoded_token.get('name', '').split()[0] if decoded_token.get('name') else ''
                user.last_name = decoded_token.get('name', '').split(' ', 1)[1] if decoded_token.get('name') and ' ' in decoded_token.get('name') else ''
                user.save()

            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.pk,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_new_user': created
                }
            })

        except Exception as e:
            return Response(
                {'error': f'Ошибка верификации токена: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _verify_google_token(self, token, request):
        """Верификация Google ID токена через Google TokenInfo API"""
        try:
            # Верифицируем токен через Google TokenInfo API
            token_info_url = f'https://oauth2.googleapis.com/tokeninfo?id_token={token}'
            response = requests.get(token_info_url, timeout=10)

            if response.status_code != 200:
                return Response(
                    {'error': 'Неверный токен'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            idinfo = response.json()

            if 'error' in idinfo:
                return Response(
                    {'error': 'Неверный токен'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем издателя токена
            issuer = idinfo.get('iss')
            if issuer not in ['accounts.google.com', 'https://accounts.google.com']:
                return Response(
                    {'error': 'Неверный издатель токена'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Проверяем audience (client ID)
            audience = idinfo.get('aud')
            expected_audience = settings.GOOGLE_CLIENT_ID

            if audience != expected_audience:
                return Response(
                    {'error': 'Токен выдан для другого приложения'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            email = idinfo.get('email')
            if not email:
                return Response(
                    {'error': 'Email не получен от Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Находим или создаём пользователя
            user, created = User.objects.get_or_create(email=email)

            if created:
                user.is_active = True
                user.first_name = idinfo.get('given_name', '')
                user.last_name = idinfo.get('family_name', '')
                user.save()

            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.pk,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_new_user': created
                }
            })

        except requests.exceptions.RequestException:
            return Response(
                {'error': 'Ошибка подключения к Google'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception:
            return Response(
                {'error': 'Ошибка входа'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Auth'],
    summary='Выход',
    description='Инвалидирует refresh токен',
)
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh токен обязателен'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({'error': 'Неверный токен'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Вы вышли из системы'})


@extend_schema(
    tags=['Auth'],
    summary='Обновить токен',
    description='''Обновляет access токен используя refresh токен.

**Тело запроса:**
- `refresh` (string) — действующий refresh токен

**Возвращаемые данные:**
- `access` — новый access токен
- `refresh` — новый refresh токен (если включена ротация)''',
    request={'type': 'object', 'properties': {'refresh': {'type': 'string'}}},
    responses={
        200: {'description': 'Токены обновлены', 'content': {'application/json': {'example': {'access': 'eyJ...', 'refresh': 'eyJ...'}}}},
        400: {'description': 'Неверный или истекший refresh токен'},
        401: {'description': 'Токен в blacklist'},
    },
    examples=[
        OpenApiExample(
            'Запрос',
            value={'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'},
            request_only=True
        ),
        OpenApiExample(
            'Успешный ответ',
            value={
                'access': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ...',
                'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxfQ...'
            },
            status_codes=[200]
        ),
        OpenApiExample(
            'Истекший токен',
            value={'error': 'Refresh токен истек'},
            status_codes=[400]
        ),
        OpenApiExample(
            'Токен в blacklist',
            value={'error': 'Токен был отозван'},
            status_codes=[401]
        )
    ],
)
class RefreshTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = None

    def post(self, request):
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response(
                {'error': 'Refresh токен обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Проверяем валидность токена
            refresh = RefreshToken(refresh_token)
            
            # Создаем новый access токен
            access_token = refresh.access_token
            
            # Если включена ротация, создаем новый refresh токен
            if getattr(settings, 'SIMPLE_JWT', {}).get('ROTATE_REFRESH_TOKENS', False):
                new_refresh = refresh.__class__()
                new_refresh['user_id'] = refresh.payload.get('user_id')
                
                # Копируем claims из старого токена
                for claim in ['user_id', 'email', 'exp']:
                    if claim in refresh.payload:
                        new_refresh[claim] = refresh.payload[claim]
                
                # Черносписим старый refresh токен
                refresh.blacklist()
                
                return Response({
                    'access': str(access_token),
                    'refresh': str(new_refresh)
                })
            
            return Response({
                'access': str(access_token),
                'refresh': str(refresh)
            })
            
        except Exception as e:
            error_message = str(e)
            
            if 'Token is blacklisted' in error_message or 'blacklisted' in error_message.lower():
                return Response(
                    {'error': 'Токен был отозван'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            elif 'expired' in error_message.lower() or 'Signature has expired' in error_message:
                return Response(
                    {'error': 'Refresh токен истек'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                return Response(
                    {'error': 'Неверный refresh токен'},
                    status=status.HTTP_400_BAD_REQUEST
                )


@extend_schema(
    tags=['Auth'],
    summary='Запрос сброса пароля',
    description='Отправляет код сброса пароля на email',
)
class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Код сброса пароля отправлен на email'})


@extend_schema(
    tags=['Auth'],
    summary='Подтверждение сброса пароля',
    description='Меняет пароль по коду из email',
)
class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Пароль успешно изменён'})


@extend_schema(
    tags=['Auth'],
    summary='Удаление аккаунта',
    description='Безвозвратно удаляет аккаунт текущего пользователя',
)
class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DeleteAccountSerializer

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.delete()
        return Response({'message': 'Аккаунт удалён'}, status=status.HTTP_204_NO_CONTENT)

@extend_schema(
    tags=['Auth'],
    summary='Регистрация',
    description='Создаёт аккаунт и отправляет код подтверждения на email. Токены выдаются только после верификации.',
)
class CustomRegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CustomRegisterSerializer

    def post(self, request):
        serializer = CustomRegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            email_errors = exc.detail.get('email', [])
            if any(str(e) == '__unverified__' for e in email_errors):
                return Response(
                    {'message': 'Код подтверждения отправлен на email. Подтвердите аккаунт для входа.'},
                    status=status.HTTP_201_CREATED
                )
            raise
        user = serializer.save(request)
        return Response(
            {'message': 'Код подтверждения отправлен на email. Подтвердите аккаунт для входа.'},
            status=status.HTTP_201_CREATED
        )

@extend_schema(
    tags=['User'],
    summary='Получить профиль пользователя',
    description='Возвращает данные текущего пользователя, включая уровень скидок и бонусы',
)
class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

@extend_schema(
    tags=['User'],
    summary='Статистика рефералов',
    description='Возвращает статистику по приглашённым пользователям и накопленным бонусам',
)
class ReferralStatsView(generics.RetrieveAPIView):
    serializer_class = ReferralStatsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

@extend_schema(
    tags=['User'],
    summary='Применить реферальный код',
    description='Применяет реферальный код после регистрации (если не был применён)',
    request=ReferralCodeApplySerializer,
    responses={
        200: UserSerializer,
        400: {'description': 'Ошибка применения кода'},
    },
)
class ApplyReferralCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReferralCodeApplySerializer

    def post(self, request):
        referral_code = request.data.get('referral_code')
        user = request.user

        if user.referred_by:
            return Response({'error': 'Реферальный код уже применен'}, status=400)

        if not referral_code:
            return Response({'error': 'Код не указан'}, status=400)

        referrer = User.objects.filter(referral_code=referral_code).first()
        if not referrer:
            return Response({'error': 'Неверный реферальный код'}, status=400)

        if referrer == user:
            return Response({'error': 'Нельзя пригласить самого себя'}, status=400)

        user.referred_by = referrer
        user.save()

        return Response({'message': 'Реферальный код успешно применен'})
    
@extend_schema(
    tags=['Auth'],
    summary='Запросить код подтверждения',
    description='Отправляет 6-значный код на email пользователя',
)
class RequestVerificationCodeView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RequestVerificationCodeSerializer
    
    def post(self, request):
        serializer = RequestVerificationCodeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Код отправлен на email'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Auth'],
    summary='Подтвердить email',
    description='Активирует аккаунт по коду из email',
)
class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = VerifyEmailSerializer
    
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Email подтверждён',
                'email': user.email
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)