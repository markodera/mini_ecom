from rest_framework import serializers
from .models import CustomUser, UserProfile
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer, UserDetailsSerializer
from phonenumber_field.serializerfields import PhoneNumberField
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.socialaccount.models import SocialAccount, SocialApp
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from .utils import build_absolute_url, get_social_avatar, resolve_display_name


#  Custom User details serializer
class CustomUserDetailsSerializer(serializers.ModelSerializer):
    """
    Extended user details with custom fields
    """

    profile_picture = serializers.SerializerMethodField()
    social_accounts = serializers.SerializerMethodField()
    has_2fa = serializers.SerializerMethodField()
    date_of_birth = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    phone_verified = serializers.BooleanField(
        source="phone_number_verified", read_only=True
    )

    class Meta:
        model = CustomUser
        fields = (
            "pk",
            "email",
            "username",
            "first_name",
            "last_name",
            "display_name",
            "phone_number",
            "phone_verified",
            "date_of_birth",
            "profile_picture",
            "social_accounts",
            "has_2fa",
        )
        read_only_fields = ("email", "social_accounts", "has_2fa", "phone_verified")

    def get_profile_picture(self, obj):
        """Get profile picture url"""
        profile = getattr(obj, "profile", None)
        if profile and profile.profile_picture:
            return build_absolute_url(
                self.context.get("request"), profile.profile_picture.url
            )

        url = get_social_avatar(obj)
        if url:
            return build_absolute_url(self.context.get("request"), url)
        return None

    def get_date_of_birth(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.date_of_birth if profile else None

    def get_social_accounts(self, obj):
        """Conected social accounts"""
        account = SocialAccount.objects.filter(user=obj)
        return [
            {"provider": acc.provider, "uid": acc.uid, "date_joined": acc.date_joined}
            for acc in account
        ]

    def get_has_2fa(self, obj):
        """Check if user has 2FA"""
        from django_otp import user_has_device

        return user_has_device(obj)

    def get_display_name(self, obj):
        return resolve_display_name(obj, persist=True)


# Custom Registration serializer


class CustomRegisterSerializer(RegisterSerializer):
    """
    Custom registeration with display_name and email verification
    """

    display_name = serializers.CharField(max_length=50, required=False)
    phone_number = PhoneNumberField(required=True)

    class Meta:
        model = CustomUser
        fields = [
            "email",
            "username",
            "phone_number",
            "password1",
            "password2",
            "display_name",
        ]

    def validate_email(self, value):
        value = value.lower().strip()
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this email address already exist. "
                "Please use a different email or try logging in."
            )
        return value

    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError(
                {"phone_number": "This field is required"}
            )
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "A user with this Phone number already exists"
            )
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken. Please choose a different username."
            )

        if len(value) < 3:
            raise serializers.ValidationError(
                "Username must be more than 3 characters long."
            )

        if not value.replace("_", "").replace("-", "").isalnum():
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, underscores and hyphens"
            )
        return value

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["display_name"] = self.validated_data.get("display_name", "")
        data["phone_number"] = self.validated_data.get("phone_number", "")
        return data

    def save(self, request):
        """
        Save the user with custom fields.
        """
        user = super().save(request)
        user.phone_number = self.validated_data.get("phone_number", "")
        user.display_name = self.validated_data.get("display_name", "")
        user.first_name = self.validated_data.get("first_name", "")
        user.last_name = self.validated_data.get("last_name", "")
        user.save()
        # Send verification email
        email_address, _ = EmailAddress.objects.get_or_create(
            user=user, email=user.email, defaults={"primary": True, "verified": False}
        )
        confirmation = EmailConfirmationHMAC(email_address)
        confirmation.send(request)
        return user


class CustomLoginSerializer(LoginSerializer):
    """
    Login with email verification and 2FA check
    """

    def validate(self, attrs):
        # First, Validate credentials
        username = attrs.get("username")
        email = attrs.get("email")
        password = attrs.get("password")

        # Get user
        user = None

        if email:
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                pass

        if not user and username:
            try:
                user = CustomUser.objects.get(username=username)
            except CustomUser.DoesNotExist:
                pass
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        # Check user password
        if not user.check_password(password):
            raise serializers.ValidationError("Invalid credentials")
        # Check email verification
        try:
            email_address = EmailAddress.objects.get(user=user, email=user.email)
            if not email_address.verified:
                raise serializers.ValidationError(
                    {
                        "detail": "Please verify your email before logging in",
                        "verification_required": True,
                    }
                )
        except EmailAddress.DoesNotExist:
            # If No EmailAdresss email not verified
            raise serializers.ValidationError(
                {
                    "detail": "Please verify your email before logging in",
                    "verification_required": True,
                }
            )
        # Acticate user if ot active
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        # Check if user has enabled 2FA
        from django_otp import user_has_device

        if user_has_device(user):
            from rest_framework.exceptions import ValidationError as DRFValidationError

            error = DRFValidationError(
                {
                    "detail": "2FA verification required",
                    "requires_2fa": True,
                    "user_id": user.id,
                }
            )
            error.status_code = 202
            raise error

        attrs["user"] = user
        return attrs


class UserBasicSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "display_name",
            "email",
            "phone_number",
            "first_name",
            "last_name",
        ]
        read_only_fields = ["id", "username", "email"]

    def get_display_name(self, obj):
        return resolve_display_name(obj, persist=True)


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(required=False)
    user_first_name = serializers.CharField(required=False, write_only=True)
    user_last_name = serializers.CharField(required=False, write_only=True)
    user_display_name = serializers.CharField(required=False, write_only=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "user",
            "bio",
            "profile_picture",
            "gender",
            "date_of_birth",
            "user_first_name",
            "user_last_name",
            "user_display_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make DOB read only if it"s already set
        if self.instance and self.instance.date_of_birth:
            self.fields["date_of_birth"].read_only = True

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None) or {}
        if "user_first_name" in validated_data:
            user_data["first_name"] = validated_data.pop("user_first_name")
        if "user_last_name" in validated_data:
            user_data["last_name"] = validated_data.pop("user_last_name")
        if "user_display_name" in validated_data:
            user_data["display_name"] = validated_data.pop("user_display_name")

        if user_data:
            u = instance.user
            for field in ("first_name", "last_name", "display_name"):
                if field in user_data:
                    setattr(u, field, user_data[field])
            changed = [
                f for f in ("first_name", "last_name", "display_name") if f in user_data
            ]
            if changed:
                u.save(update_fields=changed)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")

        profile_picture = data.get("profile_picture")
        if profile_picture:
            data["profile_picture"] = build_absolute_url(request, profile_picture)
        else:
            avatar = get_social_avatar(instance.user)
            data["profile_picture"] = build_absolute_url(request, avatar)

        return data


class EmailChangeSerializer(serializers.Serializer):
    """Allow email change with password verification"""

    new_email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate_new_email(self, value):
        """
        Validate new email not in user
        """

        user = self.context["request"].user
        # Check if it"s same as currenet email
        if value.lower() == user.email.lower():
            raise serializers.ValidationError("This is your current email address")

        # Check if email exist in CustomUser
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already in use.")

        # Check if email exist in EmailAdress
        if EmailAddress.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value.lower()

    def validate(self, attrs):
        user = self.context["request"].user

        if not user.check_password(attrs["password"]):
            raise serializers.ValidationError({"password": "Incorrect password"})
        return attrs


class ResendVerificationEmailSerializer(serializers.Serializer):
    """
    Resend verificatioin email
    """

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """
        Validate that email belongs to the user and is ot verified
        """
        user = self.context["request"].user

        if value.lower() != user.email.lower():
            raise serializers.ValidationError(
                "This email does not match your account email."
            )

        try:
            email_address = EmailAddress.objects.get(user=user, email__iexact=value)
            if email_address.verified:
                raise serializers.ValidationError("This email is already verified.")
        except EmailAddress.DoesNotExist:
            pass

        return value.lower()


class PhoneNumberSerializer(serializers.Serializer):
    """
    Request Phone number verification code
    """

    phone_number = PhoneNumberField()

    def validate_phone_number(self, value):
        """validate phone number"""

        phone_str = str(value)
        # Check if phonen is already verified
        if (
            CustomUser.objects.filter(
                phone_number=phone_str, phone_number_verified=True
            )
            .exclude(pk=self.context["request"].user.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                _("This phone number is already verified"),
                code="phone_already_verified",
            )

        return value

    def validate(self, attrs):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                _("Authentication required to verify phone number"),
                code="authentication_required",
            )
        return attrs


class PhoneVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying phone number with OTP
    """

    phone_number = PhoneNumberField(
        help_text=_("Phone number that received verification code")
    )
    code = serializers.CharField(
        min_length=6,
        max_length=6,
        help_text=_("6-digit verification code sent via SMS"),
    )

    def validate_code(self, value):
        """Validate code fomat (must be 6 digits)"""
        if not value.isdigit():
            raise serializers.ValidationError(
                _("Verification code must contain only digits."),
                code="invalid_code_fomar",
            )
        if len(value) != 6:
            raise serializers.ValidationError(
                _("Verifciation code must be exactly 6 digits."),
                code="invalid_code_length",
            )

        return value

    def validate(self, attrs):
        """Additoinal validation"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                _("Authentication required to verify phone number."),
                code="authentication_required",
            )
        return attrs


class PhoneNumberUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating user"s phone number.
    """

    phone_number = PhoneNumberField(
        required=False,
        allow_blank=True,
        help_text=_("New phonr number (Leave blank to remove)"),
    )

    def validate_phone_number(self, value):
        """validate phone number"""

        phone_str = str(value)
        # Check if phonen is already verified
        if (
            CustomUser.objects.filter(
                phone_number=phone_str, phone_number_verified=True
            )
            .exclude(pk=self.context["request"].user.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                _("This phone number is already verified"),
                code="phone_already_verified",
            )

        return value

    def update(self, instance, validated_data):
        """
        Update phone number and reset verification status
        """
        phone_number = validated_data.get("phone_number")
        if phone_number:
            # Update phone number and reset verification
            instance.phone_number = str(phone_number)
            instance.phone_number_verified = False
            instance.save(update_fields=["phone_number", "phone_number_verified"])
        else:
            # Remove old phone number
            instance.phone_number = None
            instance.phone_number_verified = False
            instance.save(update_fields=["phone_number", "phone_number_verified"])

        return instance
