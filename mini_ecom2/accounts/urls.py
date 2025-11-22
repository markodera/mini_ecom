from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.ProfileView.as_view(), name="profile"),

    # Email change
    path("email/change/", views.ChangeEmailView.as_view(), name="change-email"),

    # 2FA
    path("2fa/setup/", views.TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/setup/verify/", views.TwoFactorVerifySetupView.as_view(), name="2fa-verify-setup"),
    path("2fa/verify/", views.TwoFactorVerifyView.as_view(), name="2fa-verify"),
    path("2fa/disable/", views.TwoFactorDisableView.as_view(), name="2fa-disable"),
    path("2fa/status/", views.TwoFactorVerifyStatusView.as_view(), name="2fa-status"), 

    # Phone verification
    path("phone/send-code/", views.send_verification_code, name="phone-send-code"),
    path("phone/verify/", views.verify_phone_number, name="phone-verify"),
    path("phone/status/", views.phone_verification_status, name="phone-status"),
    path("phone/update/", views.update_phone_number, name="phone-update"),
    path("phone/remove/", views.remove_phone_number, name="phone-remove")
]
