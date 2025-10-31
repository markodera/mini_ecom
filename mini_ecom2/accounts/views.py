from rest_framework.response import Response
from rest_framework import status
from .serializers import (
    CustomUserSerializer,
    UserProfileSerializer,
    EmailChangeSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerficationConfirmSerializer,
    EmailVerificationSerializer,
)
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from .throttle import SignupRateThrottle, LoginRateThrottle, PasswordResetRateThrottle
from .models import UserProfile, CustomUser


class RegisterView(CreateAPIView):
    serializer_class = CustomUserSerializer
    throttle_classes = [SignupRateThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "detail": "Registration successful! Please check your email to verify your account.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Please provide an email and password"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
            )

        # Check password manually
        if not user.check_password(password):
            return Response(
                {"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_verified:
            return Response(
                {"detail": "Please verifiy your email before logging in."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Activate user if verified and not activated through url
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        # Only create token for verified email
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "token": token.key,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(
            {"message": "Successfully logged out"}, status=status.HTTP_200_OK
        )


class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class ChangeEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EmailChangeSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Email updated succesfully"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            # Remove or Invalidate old token
            request.user.auth_token.delete()
            # Create new token
            from rest_framework.authtoken.models import Token

            Token.objects.create(user=request.user)
            return Response(
                {"detail": "Password change succsefully. Please login again"},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    """ "Request password reset link"""

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """Confirm Password reset with token"""

    permission_classes = [AllowAny]  # No auth needed for reset

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Password reset succsesfullly. You can login now"},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationView(APIView):
    """Verfy email with token"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerficationConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Email verification successfully! You can now login."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationEmailView(APIView):
    """Resend verfication link"""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"email": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user = CustomUser.objects.get(email=email)

            if user.is_verified:
                return Response(
                    {"detail": "Email is already verified."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Resend verfication email
            email_verifier = EmailVerificationSerializer()
            email_verifier.send_verification_email(user)

            return Response(
                {"detail": "Verification email sent."}, status=status.HTTP_200_OK
            )
        except CustomUser.DoesNotExist:
            # Don't reveal email exists

            return Response(
                {"detail": "If email exists, a verfication link has been sent. "},
                status=status.HTTP_200_OK,
            )
