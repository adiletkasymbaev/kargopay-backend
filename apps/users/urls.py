from django.urls import path
from .views import (
    CustomRegisterView,
    UserProfileView, UserProfileUpdateView,
    ReferralStatsView,
    ApplyReferralCodeView,
    RequestVerificationCodeView,
    VerifyEmailView,
    LoginView, LogoutView, RefreshTokenView,
    PasswordResetRequestView, PasswordResetConfirmView,
    DeleteAccountView,
    GoogleLoginView,
)

urlpatterns = [
    path('registration/', CustomRegisterView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='user-profile-update'),
    path('referral/stats/', ReferralStatsView.as_view(), name='referral-stats'),
    path('referral/apply/', ApplyReferralCodeView.as_view(), name='apply-referral'),
    path('verification/request/', RequestVerificationCodeView.as_view(), name='verification-request'),
    path('verification/confirm/', VerifyEmailView.as_view(), name='verification-confirm'),
    path('login/', LoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('refresh/', RefreshTokenView.as_view(), name='token-refresh'),
    path('password/reset/', PasswordResetRequestView.as_view()),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view()),
    path('delete/', DeleteAccountView.as_view()),
    path('google/', GoogleLoginView.as_view(), name='google-login'),
]