from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    UserProfileSerializer,
    EmailChangeSerializer,
    ResendVerificationEmailSerializer
)
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.core.exceptions import ImmediateHttpResponse
from django.db import transaction
from .models import UserProfile, CustomUser
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import user_has_device
import qrcode  
from io import BytesIO
import base64

from dj_rest_auth.views import LoginView as DjRestAuthLoginView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice

class GoogleLogin(SocialLoginView): 
    adapter_class = GoogleOAuth2Adapter
    callback_url = settings.FRONTEND_URL
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        # If user has 2fa verification step
        if 'otp_verified' in request.data and 'user_id' in  request.data:
            return self.verify_2fa_and_login(request)
        
        # Else proceed with normal login
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except ImmediateHttpResponse as e :
            return e.response
     
    def verify_2fa_and_login(self, request):
        """Verify 2FA Token and complete login"""
        user_id = request.data.get('user_id')
        # Normalize the supplied token so .strip() never errors on None
        otp_token = (request.data.get('otp_token') or "").strip().replace(' ', '')

        if not user_id or not otp_token:
            return Response(
                {"detail": "User ID and token required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        session_user_id =  request.session.get('pending_social_login_user_id')
        if not session_user_id or str(session_user_id) != str(user_id):
            return Response(
                {"detail": "Invalid session or user ID mismatch"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
           user = CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return Response(
                {"detail": "User not found"}
            )
        
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
        from rest_framework_simplejwt.tokens import RefreshToken
        from .serializers import CustomUserDetailsSerializer

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        request.session['otp_verified'] = True
        
        # Clean up 2FA seeion verification
        provider = request.session.pop('social_provider', 'google')
        request.session.pop('pending_social_login_user_id', None)
        request.session.pop('requires_2fa', None)

        # Generate JWT tokens 

        refresh = RefreshToken.for_user(user)
        serializer = CustomUserDetailsSerializer(user, context={'request': request})

        response_data = {
            "detail": f"{provider.title()} login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": serializer.data
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
        # Normalize the supplied token so .strip() never errors on None
        otp_token = (request.data.get('otp_token') or "").strip().replace(' ', '')

        if not user_id or not otp_token:
            return Response(
                {"detail": "Invalid user"},
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