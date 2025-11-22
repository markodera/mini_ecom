from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from django_otp import user_has_device
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):

    """
    Custom adapter for API redirect
    """

    def is_open_for_signup(self, request):
        return True

    def save_user(self, request, user, form, commit=True):
        """
        Persist the user via parent class then mark inactive user. Email confirmation is triggered by allalluth we filp the flag.
        """

        user = super().save_user(request, user, form, commit=True)

        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return user

    def respond_user_inactive(self, request, user):
        """Return JSON for inactive users"""
        return JsonResponse(
            {
                "detail": "User account is inactive. Please verify email address.",
                "verification_required": True,
                "email": user.email,
            },
            status=403,
        )

    def clean_email(self, email):
        email = super().clean_email(email)
        if EmailAddress.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email address already exists.")
        return email

    def get_login_redirect_url(self, request):
        """ "No redirects for APIs"""
        return None

    def get_email_verification_redirect_url(self, email_address):
        """No redirects for API"""
        return None


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapters
    """

    def populate_user(self, request, sociallogin, data):
        """
        Populate adapter fields for socail provider data
        Called before save
        """
        user = super().populate_user(request, sociallogin, data)

        provider = sociallogin.account.provider

        if provider == "google":
            user.first_name = data.get("given_name", "")
            user.last_name = data.get("family_name", "")

        elif provider == "facebook":
            user.first_name = data.get("first_name", "")
            user.last_name = data.get("last_name", "")

        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        # Only set dispaly name if non available
        if not user.display_name:
            provider = sociallogin.account.provider
            extra_data = sociallogin.account.extra_data
            if provider == "google":
                user.display_name = (
                    sociallogin.account.extra_data.get("name")
                    or f"{user.first_name} {user.last_name}".strip()
                    or user.email.split("@")[0]
                )
            elif provider == "facebook":
                user.display_name = (
                    extra_data.get("name")
                    or extra_data.get("short_name")
                    or f"{user.first_name} {user.last_name}".strip()
                    or user.email.split("@")[0]
                )
            if user.display_name:
                user.save(update_fields=["display_name"])

        return user

    def _enforce_social_2fa(self, request, user, provider):
        """Return a 202 challenge whenever a confirmed OTP device exists."""

        if not user or not getattr(user, "pk", None):
            logger.debug("Skipping 2FA enforcement because user or primary key missing")
            return False

        has_confirmed_device = user_has_device(user, confirmed=True)
        logger.debug(
            "2FA enforcement check: user=%s provider=%s confirmed_device=%s otp_verified_session=%s",
            getattr(user, "pk", None),
            provider,
            has_confirmed_device,
            request.session.get("otp_verified"),
        )

        if has_confirmed_device:
            logger.debug(
                "Enforcing social 2FA; raising challenge (user=%s provider=%s)",
                getattr(user, "pk", None),
                provider,
            )
            request.session["pending_social_login_user_id"] = user.pk
            request.session["requires_2fa"] = True
            request.session["social_provider"] = provider

            raise ImmediateHttpResponse(
                JsonResponse(
                    {
                        "detail": "2FA verification required",
                        "requires_2fa": True,
                        "user_id": user.pk,
                        "provider": provider,
                    },
                    status=202,
                )
            )

        return False

    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)

        if sociallogin.account.user_id is None:
            return

        user = sociallogin.account.user
        provider = sociallogin.account.provider

        logger.debug(
            "pre_social_login: is_existing=%s user=%s provider=%s",
            getattr(sociallogin, "is_existing", None),
            getattr(user, "pk", None),
            provider,
        )

        if sociallogin.is_existing:
            self._enforce_social_2fa(request, user, provider)

        # When the social account is being created in this request, ensure we
        # still enforce 2FA if the resolved Django user already has devices.
        if not sociallogin.is_existing and user_has_device(user, confirmed=True):
            logger.debug(
                "pre_social_login detected device for new social account (user=%s)",
                getattr(user, "pk", None),
            )
            self._enforce_social_2fa(request, user, provider)

    def login(self, request, sociallogin):
        user = sociallogin.user
        provider = sociallogin.account.provider

        if not request.session.get("otp_verified"):
            try:
                self._enforce_social_2fa(request, user, provider)
            except ImmediateHttpResponse:
                logger.debug(
                    "Social login paused for 2FA verification (user=%s, provider=%s)",
                    getattr(user, "pk", None),
                    provider,
                )
                raise

        return super().login(request, sociallogin)
