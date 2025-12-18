from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, RequestFactory
from rest_framework import status
from rest_framework.test import APIRequestFactory

from allauth.socialaccount.models import SocialAccount
from allauth.core.exceptions import ImmediateHttpResponse

from .adapters import CustomSocialAccountAdapter
from .models import CustomUser, UserProfile
from .serializers import UserProfileSerializer, CustomUserDetailsSerializer
from .views import GoogleLogin
from django_otp.plugins.otp_totp.models import TOTPDevice


class CustomSocialAccountAdapterTests(TestCase):
    def setUp(self):
        self.adapter = CustomSocialAccountAdapter()
        self.factory = RequestFactory()
        self.request = self.factory.post("/api/auth/google/")

    @staticmethod
    def _attach_session(request):
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request

    @staticmethod
    def _build_sociallogin(provider="google", extra_data=None):
        account = SimpleNamespace(
            provider=provider, extra_data=extra_data or {})
        return SimpleNamespace(account=account)

    def test_save_user_sets_display_name_for_google(self):
        """Exercising CustomSocialAccountAdapter.save_user for Google."""

        user = CustomUser.objects.create_user(
            username="mark",
            email="mark@example.com",
            password="pass12345",
        )
        user.display_name = ""
        user.save(update_fields=["display_name"])

        sociallogin = self._build_sociallogin("google", {"name": "Mark G"})

        with patch(
            "accounts.adapters.DefaultSocialAccountAdapter.save_user",
            return_value=user,
        ):
            updated_user = self.adapter.save_user(self.request, sociallogin)

        self.assertEqual(
            updated_user.display_name,
            "Mark G",
            "Google OAuth should populate display_name via save_user",
        )

    def test_pre_social_login_blocks_when_device_exists_even_if_not_flagged_existing(
        self,
    ):
        """Ensure we still raise 202 when the sociallogin object lacks the existing flag."""

        user = CustomUser.objects.create_user(
            username="2fa-social",
            email="2fa-social@example.com",
            password="pass12345",
        )
        TOTPDevice.objects.create(user=user, name="default", confirmed=True)

        sociallogin = SimpleNamespace(
            is_existing=False,
            account=SimpleNamespace(user=user, user_id=user.id, provider="google"),
        )

        request = self._attach_session(self.factory.post("/api/auth/google/"))

        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)

        self.assertEqual(ctx.exception.response.status_code,
                         status.HTTP_202_ACCEPTED)
        self.assertTrue(request.session.get("requires_2fa"))


class GoogleLogin2FATests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = CustomUser.objects.create_user(
            username="2fa-user",
            email="2fa@example.com",
            password="pass12345",
        )

    @staticmethod
    def _attach_session(request):
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_google_login_2fa_session_check_never_passes(self):
        """verify_2fa_and_login should reach token verification when session matches."""

        request = self.factory.post(
            "/api/auth/google/",
            {
                "user_id": self.user.id,
                "otp_token": "123456",
            },
            format="json",
        )

        request = self._attach_session(request)
        request.session["pending_social_login_user_id"] = str(self.user.id)

        view = GoogleLogin.as_view()

        with patch("accounts.views.TOTPDevice.objects.get") as mock_totp_get:
            mock_totp_get.return_value = SimpleNamespace(
                verify_token=lambda token: True
            )

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data.get("detail"),
            "Google login successful",
            "2FA flow should finish successfully when session matches.",
        )

    def test_google_login_accepts_token_alias(self):
        """2FA verification should succeed when client sends `token` instead of `otp_token`."""

        request = self.factory.post(
            "/api/auth/google/",
            {
                "user_id": self.user.id,
                "token": "654321",
            },
            format="json",
        )

        request = self._attach_session(request)
        request.session["pending_social_login_user_id"] = str(self.user.id)

        view = GoogleLogin.as_view()

        with patch("accounts.views.TOTPDevice.objects.get") as mock_totp_get:
            mock_totp_get.return_value = SimpleNamespace(
                verify_token=lambda token: True
            )

            response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserProfileSerializerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = CustomUser.objects.create_user(
            username="profile-user",
            email="profile@example.com",
            password="pass12345",
            first_name="Profile",
            last_name="User",
        )

        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="google-profile",
            extra_data={
                "name": "Profile User",
                "picture": "https://example.com/avatar.png",
            },
        )
        # Ensure the profile exists (signal should create it, but keep it explicit in tests)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_profile_picture_falls_back_to_social_avatar(self):
        request = self.factory.get("/api/accounts/profile/")

        serializer = UserProfileSerializer(
            instance=self.profile,
            context={"request": request},
        )

        self.assertEqual(
            serializer.data["profile_picture"],
            "https://example.com/avatar.png",
            "Serializer should surface the social avatar when no upload exists.",
        )

    def test_display_name_fallback_uses_name_components(self):
        self.user.display_name = ""
        self.user.save(update_fields=["display_name"])

        request = self.factory.get("/api/accounts/profile/")
        serializer = UserProfileSerializer(
            instance=self.profile,
            context={"request": request},
        )

        self.assertEqual(
            serializer.data["user"]["display_name"],
            "Profile User",
            "UserBasicSerializer should compose display_name when missing.",
        )


class CustomUserDetailsSerializerTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = CustomUser.objects.create_user(
            username="details-user",
            email="details@example.com",
            password="pass12345",
            first_name="Details",
            last_name="User",
        )

    def test_display_name_matches_profile_serializer(self):
        self.user.display_name = ""
        self.user.save(update_fields=["display_name"])

        request = self.factory.get("/api/auth/user/")
        serializer = CustomUserDetailsSerializer(
            instance=self.user,
            context={"request": request},
        )

        self.assertEqual(
            serializer.data["display_name"],
            "Details User",
            "CustomUserDetailsSerializer should use the same fallback logic as profile endpoint.",
        )
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.display_name,
            "Details User",
            "Serializer access should persist fallback display name to the database.",
        )

    def test_display_name_uses_explicit_value(self):
        self.user.display_name = "Preferred"
        self.user.save(update_fields=["display_name"])

        serializer = CustomUserDetailsSerializer(instance=self.user)
        self.assertEqual(
            serializer.data["display_name"],
            "Preferred",
            "Serializer must respect custom display names when provided.",
        )
