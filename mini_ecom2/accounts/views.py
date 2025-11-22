import logging
from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    UserProfileSerializer,
    EmailChangeSerializer,
    ResendVerificationEmailSerializer,
    PhoneNumberSerializer,
    PhoneVerificationSerializer,
    PhoneNumberUpdateSerializer
)
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.decorators import api_view, permission_classes
from django.utils.translation import  gettext_lazy as _
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.core.exceptions import ImmediateHttpResponse
from django.db import transaction
from .models import UserProfile, CustomUser
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import user_has_device
import qrcode  
from io import BytesIO
import base64
from .sms import SMSService, send_phone_verification
from dj_rest_auth.views import LoginView as DjRestAuthLoginView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client, OAuth2Error
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice

logger = logging.getLogger(__name__)
class SocialLogin2FAMixin:
    """Shared helpers for social OAuth flows that require 2FA."""

    provider_name = "social"

    def post(self, request, *args, **kwargs):
        # Always clear any previous OTP flag before starting a fresh social login
        request.session.pop("otp_verified", None)

        if "otp_verified" in request.data and "user_id" in request.data:
            return self.verify_2fa_and_login(request)

        try:
            response = super().post(request, *args, **kwargs)
        except ImmediateHttpResponse as exc:
            self.logger.debug(
                "Social login intercepted for provider=%s status=%s payload=%s",
                getattr(self, "provider_name", "social"),
                getattr(exc.response, "status_code", None),
                getattr(exc.response, "content", b"").decode("utf-8", errors="ignore"),
            )
            return exc.response
        except OAuth2Error as exc:
            # Provider token exchange failed or user info endpoint rejected the request
            provider = getattr(self, "provider_name", "social").title()
            return Response(
                {
                    "detail": f"{provider} token validation failed",
                    "error": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.session.get("requires_2fa") and not request.session.get("otp_verified"):
            from django.contrib.auth import logout

            user_id = request.session.get("pending_social_login_user_id")
            provider = request.session.get("social_provider", self.provider_name)

            self.logger.debug(
                "Social login response converted to 202 (user=%s provider=%s)",
                user_id,
                provider,
            )

            session_snapshot = {
                "pending_social_login_user_id": user_id,
                "requires_2fa": True,
                "social_provider": provider,
            }

            logout(request)

            for key, value in session_snapshot.items():
                if value is not None:
                    request.session[key] = value

            request.session.modified = True
            try:
                request.session.save()
            except Exception:
                self.logger.debug("Social login session save skipped", exc_info=True)

            challenge_payload = {
                "detail": "2FA verification required",
                "requires_2fa": True,
                "user_id": user_id,
                "provider": provider,
            }

            return Response(challenge_payload, status=status.HTTP_202_ACCEPTED)

        return response

    def verify_2fa_and_login(self, request):
        """Verify the submitted OTP token and finish the login."""

        user_id = request.data.get("user_id")
        raw_otp = request.data.get("otp_token") or request.data.get("token")
        otp_token = (raw_otp or "").strip().replace(" ", "")

        if not user_id or not otp_token:
            return Response(
                {"detail": "User ID and token required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session_user_id = request.session.get("pending_social_login_user_id")
        self.logger.debug(
            "Verifying social 2FA: session_id=%s payload_user=%s session_user=%s session_key=%s",
            request.session.session_key,
            user_id,
            session_user_id,
            getattr(request.session, "session_key", None),
        )
        if not session_user_id or str(session_user_id) != str(user_id):
            return Response(
                {"detail": "Invalid session or user ID mismatch"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return Response({"detail": "User not found"})

        if otp_token.isdigit() and len(otp_token) == 6:
            try:
                device = TOTPDevice.objects.get(user=user, confirmed=True)
                if device.verify_token(otp_token):
                    return self.complete_login(request, user, is_backup=False)
            except TOTPDevice.DoesNotExist:
                pass

        try:
            static_device = StaticDevice.objects.get(user=user, name="backup")
            if static_device.verify_token(otp_token):
                return self.complete_login(request, user, is_backup=True)
        except StaticDevice.DoesNotExist:
            pass

        return Response(
            {"detail": "Invalid 2FA token."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def complete_login(self, request, user, is_backup=False):
        """Issue tokens and cookies once 2FA succeeds."""

        from .serializers import CustomUserDetailsSerializer

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session["otp_verified"] = True

        provider = request.session.pop("social_provider", self.provider_name)
        request.session.pop("pending_social_login_user_id", None)
        request.session.pop("requires_2fa", None)

        refresh = RefreshToken.for_user(user)
        serializer = CustomUserDetailsSerializer(user, context={"request": request})

        response_data = {
            "detail": f"{provider.title()} login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": serializer.data,
        }

        if is_backup:
            response_data["warning"] = "Backup code used. Please generate new backup codes"

        response = Response(response_data, status=status.HTTP_200_OK)

        from datetime import datetime, timezone

        access_token_expiration = datetime.now(timezone.utc) + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        refresh_token_expiration = datetime.now(timezone.utc) + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']

        response.set_cookie(
            key=settings.REST_AUTH['JWT_AUTH_COOKIE'],
            value=str(refresh.access_token),
            expires=access_token_expiration,
            httponly=settings.REST_AUTH['JWT_AUTH_HTTPONLY'],
            samesite=settings.REST_AUTH['JWT_AUTH_SAMESITE'],
            secure=not settings.DEBUG
        )
        response.set_cookie(
            key=settings.REST_AUTH['JWT_AUTH_REFRESH_COOKIE'],
            value=str(refresh),
            expires=refresh_token_expiration,
            httponly=settings.REST_AUTH['JWT_AUTH_HTTPONLY'],
            samesite=settings.REST_AUTH['JWT_AUTH_SAMESITE'],
            secure=not settings.DEBUG
        )

        return response


class GoogleLogin(SocialLogin2FAMixin, SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    
    callback_url = settings.FRONTEND_URL
    client_class = OAuth2Client
    provider_name = "google"


class FacebookLogin(SocialLogin2FAMixin, SocialLoginView):
    adapter_class = FacebookOAuth2Adapter
    callback_url = settings.FRONTEND_URL
    client_class = OAuth2Client
    provider_name = "facebook"


class CustomLoginView(DjRestAuthLoginView):
    """Custom login vire with 2FA support"""

    def post(self, request, *args, **kwargs):
        # If user has 2fa verification step
        if 'otp_verified' in request.data and 'user_id' in  request.data:
            return self.verify_2fa_and_login(request)
        
        # Else proceed with normal login
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except Exception as e :
            if hasattr(e, "detail")  and isinstance(e.detail, dict):
                if e.detail.get("requires_2fa"):
                    return Response(e.detail, status=status.HTTP_202_ACCEPTED)
                raise
    
    def verify_2fa_and_login(self, request):
        """Verify 2FA Token and complete login"""


        user_id = request.data.get('user_id')
        # Accept both otp_token and token payload keys for client flexibility
        raw_otp = request.data.get('otp_token') or request.data.get('token')
        otp_token = (raw_otp or "").strip().replace(' ', '')

        if not user_id or not otp_token:
            return Response(
                {"detail": "User ID and token required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
           user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "Invalid user"}
            )
        
        # Check if user is acive
        if not user.is_active:
            return Response(
                {"detail": "User account disabled"},
                status=status.HTTP_403_FORBIDDEN
            )
        # Totp first (6 digits)
        verified = False
        is_backup = False
        if otp_token.isdigit() and len(otp_token) == 6:
            try:
                device =  TOTPDevice.objects.get(user=user, confirmed=True)
                if device.verify_token(otp_token):
                    
                    return self.complete_login(request, user, is_backup=False)
            except TOTPDevice.DoesNotExist:
                pass
        # Try backup
        try: 
            static_device = StaticDevice.objects.get(user=user, name="backup")
            if static_device.verify_token(otp_token):
                return self.complete_login(request, user, is_backup=True)
        except StaticDevice.DoesNotExist:
            pass

        return Response(
            {"detail": "Invalid 2FA token."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def complete_login(self, request, user, is_backup=False):
        """Complete login for successful 2FA verfication"""

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        
        # Mark OTP as verified in session 
        request.session["otp_verified"] = True

        # Generate refresh token
        refresh = RefreshToken.for_user(user)

        response_data = {
            "detail": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "display_name": user.display_name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }

        if is_backup:
            response_data["warning"] = "Backup code used. Please generate new backup codes"

        # Always send a new response so both standard and backup paths behave the same
        response = Response(response_data, status=status.HTTP_200_OK)

        from datetime import datetime, timezone
        from django.conf import settings

        # Use the configured lifetimes to mirror SIMPLE_JWT settings for cookies
        access_token_expiration = datetime.now(timezone.utc) + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        refresh_token_expiration = datetime.now(timezone.utc) + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']

        # Store each token in the dedicated cookie expected by dj-rest-auth
        response.set_cookie(
            key=settings.REST_AUTH['JWT_AUTH_COOKIE'],
            value=str(refresh.access_token),
            expires=access_token_expiration,
            httponly=settings.REST_AUTH['JWT_AUTH_HTTPONLY'],
            samesite=settings.REST_AUTH['JWT_AUTH_SAMESITE'],
            secure=not settings.DEBUG
        )
        response.set_cookie(
            key=settings.REST_AUTH['JWT_AUTH_REFRESH_COOKIE'],
            value=str(refresh),
            expires=refresh_token_expiration,
            httponly=settings.REST_AUTH['JWT_AUTH_HTTPONLY'],
            samesite=settings.REST_AUTH['JWT_AUTH_SAMESITE'],
            secure=not settings.DEBUG
        )

        return response
class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class ChangeEmailView(APIView):

    """Change user's email address"""
    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = EmailChangeSerializer(
            data=request.data, 
            context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
                )
        new_email = serializer.validated_data['new_email']
        user = request.user
        old_email = user.email

        try:
            with transaction.atomic():
                # Delete old EmailAddress is entry exists
                EmailAddress.objects.filter(user=user).delete()

                # Update user's email but keep account inactive until verified

                user.email = new_email
                user.is_active = False
                user.save()

                # Create new unverified EmailAdress entry
                email_address = EmailAddress.objects.create(
                    user=user,
                    email=new_email,
                    primary=True,
                    verified=False,
                )

                # Send verification email
                confirmation = EmailConfirmationHMAC(email_address)
                confirmation.send(request)

            return Response({
                "detail": "Email change successful. Please verify your new email address.",
                "old_email": old_email,
                "new_email": new_email,
                "verification_sent": True
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "detail": f"Failed to change email: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResendVerificationEmailView(APIView):
    """
    Resend confirmation email for unverified email address
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):

        """
        Resend verification email
        """

        serializer = ResendVerificationEmailSerializer(
            data=request.data,
            context={"request": request}
        )
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data['email']
        user = request.user

        # Check if email is inactive and pending verification

        if not user.is_active:
            try:
                # Get EmailAddress entry
                email_address = EmailAddress.objects.get(
                    user=user,
                    email__iexact=email,
                )

                if email_address.verified:
                    return Response({
                        "detail": "Your email is already verified."
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                #  Send verification email using HMAC

                confirmation = EmailConfirmationHMAC(email_address)
                confirmation.send(request)

                return Response({
                    "detail": "Verification email sent.", 
                    "email": email
                },status=status.HTTP_200_OK)

            except EmailAddress.DoesNotExist:
                return Response({
                    "detail": "If this email exist, Verification email sent"
                }, status=status.HTTP_200_OK)
class TwoFactorSetupView(APIView):
    """Generate QR code or 2Fa setup"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user_has_device(user):
            return Response(
                {"detail": "2FA is already enabled"},
                status=status.HTTP_400_BAD_REQUEST
            )
        device = TOTPDevice.objects.create(
            user=user,
            name='default',
            confirmed=False
        )

        url = device.config_url


        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return Response({
            "qr_code": f"data:image/png;base64,{img_str}",
            "secret": device.key,
            "device_id":device.id
        })
    
class TwoFactorVerifySetupView(APIView):
    """Verify 2FA token to complete setup"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        token = request.data.get('token', '').strip().replace(' ', '')
        device_id = request.data.get('device_id')

        if not token:
            return Response(
                {"error": "Token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not token.isdigit() or len(token) != 6:
            return Response(
                {"error": "Token must be a 6-digit code"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            device = TOTPDevice.objects.get(
                id = device_id,
                user=user,
                confirmed=False
            )
        except TOTPDevice.DoesNotExist:
            return Response(
                {"error": "Invalid device"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            return Response({
                "detail": "2FA enabled successfully",
                "backup_codes": self.generate_backup_codes(user)
            })
        else:
            return Response(
                {"error": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST
            )
    def generate_backup_codes(self, user):
        from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
        
        device, created = StaticDevice.objects.get_or_create(
            user=user,
            name='backup'
        )

        device.token_set.all().delete()

        codes = []
        for _ in range(10):
            token = StaticToken.random_token()
            device.token_set.create(token=token)
            codes.append(token)
        return codes
    
class TwoFactorVerifyView(APIView):
    """"Verify 2FA token during login"""
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        token_input = request.data.get('token', '')
        if isinstance(token_input, list):
            if not token_input:
                return Response(
                    {"error": "Token is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = str(token_input[0]).strip.replace(' ', '')
        else:
            token = str(token_input).strip.replace(' ', '')
        if not token_input:
                return Response(
                    {"error": "Token is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Check if it's a TOTP token (6 digits)
        if token.isdigit() and len(token) == 6:
            try:
                device = TOTPDevice.objects.get(user=user, confirmed=True)
                if device.verify_token(token):
                    request.session['otp_verified'] = True
                    return Response({"detail": "2FA verification successful"})
            except TOTPDevice.DoesNotExist:
                return Response(
                    {"error": "2FA not enabled"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        
        # Try backup code if TOTP failed or token is not 6 digits
        from django_otp.plugins.otp_static.models import StaticDevice
        try:
            static_device = StaticDevice.objects.get(user=user, name='backup')
            if static_device.verify_token(token):
                request.session['otp_verified'] = True
                return Response({
                    "detail": "2FA verification successful (backup code used)",
                    "warning": "Please generate new backup codes"
                })
        except StaticDevice.DoesNotExist:
            pass

        return Response(
            {"error": "Invalid token"},
            status=status.HTTP_400_BAD_REQUEST
        )
class TwoFactorDisableView(APIView):
    """Disable 2FA for users"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        password = request.data.get('password')

        if not user.check_password(password):
            return Response(
                {"error": "Invalid password"},
                status=status.HTTP_400_BAD_REQUEST
            )
        TOTPDevice.objects.filter(user=user).delete()
        from django_otp.plugins.otp_static.models import StaticDevice
        StaticDevice.objects.filter(user=user).delete()

        return Response({"detail": "2FA disabled successfully"})

class TwoFactorVerifyStatusView(APIView):
    """Check if user has 2FA enabled"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        has_2fa = user_has_device(user)

        return Response({
            "2fa_enabled": has_2fa,
            "devices": TOTPDevice.objects.filter(user=user, confirmed=True).count()
        })
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_verification_code(request):
    """
    Send SMS verification code to user's phone number.
    
    POST /api/accounts/phone/send-code/
    {
        "phone_number": "+2349012345678"
    }

    Returns:
        200: Code sent succsesfully
        400: Valdation error
        429: Rate limit exceeded
        500: SMS sending falied
    """
    serializer = PhoneNumberSerializer(data=request.data, context={'request':request})
    if not serializer.is_valid():
        return Response(
            {
                'detail':_('Invalid phone number.'),
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    phone_number = str(serializer.validated_data['phone_number'])
    sms_service = SMSService()

    result = send_phone_verification(request.user, phone_number, sms_service)

    if result['success']:
        # Update users phone number if different
        if request.user.phone_number != phone_number:
            request.user.phone_number = phone_number
            request.user.phone_number_verified = False
            request.user.save(update_fields=['phone_number', 'phone_number_verified']) 

            # Increment rate limit conter AFTER succesful send
            sms_service.increment_code_sent_count(phone_number)

            logger.info(
                f"Verification code sent to {phone_number[:8]}***",
                extra={'user_id': request.user.id}
            )

            return Response(
                {
                'detail': result['detail'],
                'phone_number': phone_number,
                'expires_in_minutes': result['expires_in_minutes']
                },
                status=status.HTTP_200_OK
            )

    else:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS if result["error"] == 'rate_limited' else status.HTTP_500_INTERNAL_SERVER_ERROR
            logger.info(
                f"Failed to send code to {phone_number[:8]}***: {result['error']}",
                extra={'user_id': request.user.id}
            )

            response_data = {
                'detail': result['detail'],
                'type': result['error']
            }

            if 'wait_seconds' in result:
                response_data['retry_after'] = result['wait_seconds']
            return Response(response_data, status=status_code)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_phone_number(request):
    """
    Verify phone number with OTP code.

    POST /api/accounts/phone/verify/
    {
        "phone_number": "+2349012345678",
        "code": "123456"
    }

    Returns:
        200: Phone number verified successfully
        400: invalid code or expired
        429: Too many verification attempts
    """

    serializer = PhoneVerificationSerializer(data=request.data, context={'request':request})
    if not serializer.is_valid():
        return Response(
            {
                'detail': _('Invalid verification data.'),
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    phone_number = str(serializer.validated_data['phone_number'])
    code = serializer.validated_data['code']

    sms_service = SMSService()

    # Verify the code (Include rate limiting)

    is_valid, message, is_backup = sms_service.verify_code(
        phone_number, 
        code,
        request.user.id
    )

    if not is_valid:
        logger.warring(
            f"Invalid verification attempts for {phone_number[:8]}***",
            extra={'user_id': request.user.id}
        )

        return Response(
            {
                'detail': message,
                'type': 'invalid_code'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Mark phone as verified
    request.user.phone_number = phone_number
    request.user.phone_number_verified = True
    request.user.save(update_fields=['phone_number', 'phone_number_verified'])

    logger.info(
        f"Phone verification {phone_number[:8]}*** verified successfully",
        extra={'user_id': request.user.id}
    )

    return Response(
        {
            'detail': _("Phone number verified successfully."),
            'phone_number': phone_number,
            'verified': True
        },
        status=status.HTTP_200_OK
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def phone_verification_status(request):
    """
    Get current phone verification status.

    GET /api/accounts/phone/status/

    Returns:
        200: Current Phone verification status
    """
    user = request.user
    sms_service = SMSService()

    phone_str = str(user.phone_number) if user.phone_number else None
    can_send = False
    wait_seconds = 0

    if phone_str:
        can_send, wait_seconds = sms_service.can_send_code(phone_str)

    return Response(
        {
            'phone_number': phone_str,
            'verified': user.phone_number_verified,
            'can_request_code': can_send,
            'retry_after': wait_seconds if not can_send else 0,
            'max_attempts': settings.PHONE_VERIFICATION['MAX_ATTEMPTS'],
            'code_expires_in_minutes': settings.PHONE_VERIFICATION['CODE_EXPIRY_MINUTES']
        },
        status=status.HTTP_200_OK
    )

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_phone_number(request):
    """
    Update user's phone number.

    PUT/PATCH /api/accounts/phone/update/
    {
        "phone_number": "+2349012345678"
    }

    Returns:
        200: Phone number updated successfully
        400: Invalid phone number
        403: Phone number already verified
    """
    serializer = PhoneNumberUpdateSerializer(
        instance=request.user,
        data=request.data, 
        context={'request': request},
        partial=True
        )
    if not serializer.is_valid():
        return Response(
            {
                'detail': _('Invalid phone number.'),
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = serializer.save()

    logger.info(
        f"Phone number updated for user {user.id}",
        extra={'user_id': user.id}
    )
 
    return Response(
        {
            'detail': _('Phone number updated. Please verified your new phone number.'),
            'phone_number': str(user.phone_number) if user.phone_number else None,
            'verified': user.phone_number_verified
        },
        status=status.HTTP_200_OK
    )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_phone_number(request):
    """
    Remove user's phone number.

    DELETE /api/accounts/phone/remove/

    Returns:
        200: Phone number removed successfully

    """

    user = request.user

    user.phone_number = None
    user.phone_number_verified = False
    user.save(update_fields=['phone_number', 'phone_number_verified'])

    logger.info(
        f"Phone number removed for user {user.id}",
        extra={'user_id': user.id}
    )

    return Response(
        {
            'detail': _('Phone number removed successfully.')
        },
        status=status.HTTP_200_OK
    )