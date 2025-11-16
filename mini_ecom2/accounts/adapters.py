from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from django_otp import user_has_device
from django.core.exceptions import ValidationError
from django.http import JsonResponse


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
        return JsonResponse({
            "detail": "User account is inactive. Please verify email address.",
            "verification_required": True,
            "email": user.email
        }, status=403)
    
    def clean_email(self, email):
        email =  super().clean_email(email)
        if EmailAddress.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email address already exists.")
        return email
    
    def get_login_redirect_url(self, request):
        """"No redirects for APIs"""
        return None
    
    def get_email_verification_redirect_url(self, email_address):
        
        """No redirects for API"""
        return None
    
class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapters
    """

    def populate_user(self, request, sociallogin, data):
        user =  super().populate_user(request, sociallogin, data)

        provider = sociallogin.account.provider

        if provider == 'google':

            user.first_name = data.get('given_name', '')
            user.last_name = data.get('family_name', '')

        elif provider == 'facebook':
            user.first_name = data.get('first_name', '')
            user.last_name = data.get('last_name', '')

        return user


    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if not user.display_name:
            provider = sociallogin.account.provider
            if provider == 'google':
                user.display_name = (
                    sociallogin.account.extra_data.get('name') or
                    f"{user.first_name} {user.last_name}".strip()
                    or user.email.split('@')[0]
                )
            elif provider == 'facebook':
                user.display_name = (
                    sociallogin.account.extra_data.get('name') or
                    f"{user.first_name} {user.last_name}".strip()
                    or user.email.split('@')[0]
                )
            if user.display_name:
                user.save(update_fields=['display_name'])

        return user
    
    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        # If exsiting user has 2fa
        if not sociallogin.is_existing:
            return
        user = sociallogin.account.user
        # Check if user has it enabled
        if user_has_device(user, confirmed=True):
            request.session['pending_social_login_user_id'] = user.pk
            request.session['requires_2fa'] = True
            request.session['social_provider'] = sociallogin.account.provider

            # Interrupt the OAuth flow

            raise ImmediateHttpResponse(
                JsonResponse({
                    "detail": " 2FA verifcation required",
                    "requires_2fa": True,
                    "user_id": user.pk,
                    "provider": sociallogin.account.provider
                }, status=202)
            )
        

        