from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    # Email change
    path("email/change/", views.ChangeEmailView.as_view(), name="change-email"),
    # Password Change
    path(
        "password/change/", views.ChangePasswordView.as_view(), name="password-change"
    ),
    # Password Reset
    path(
        "password/reset/request/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password/reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    # Email Verification
    path("email/verify/", views.EmailVerificationView.as_view(), name="email-verify"),
    path(
        "email/resend/",
        views.ResendVerificationEmailView.as_view(),
        name="resend-verification",
    ),
]
