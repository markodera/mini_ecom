from rest_framework import serializers
from .models import CustomUser, UserProfile
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
class WriteOnceField(serializers.Field):
    """
    A field that can only be set once. After initial creation,
    attempt to modify will raise a validation error.

    Usage:
        date_of_birth = WriteOnceField(
        child=serializers.DateField(),
        required=False,
        allow_null=True
        )
    """
    def __init__(self, **kwargs):
        self.child = kwargs.pop('child', serializers.CharField())
        super().__init__(**kwargs)

    def to_representation(self, value):
        return self.child.to_representation(value)
    
    def to_internal_value(self, data):
        return self.child.to_internal_value(data)
    
    def validate_empty_values(self, data):
        # Allow empty on create, but not on update if already set
        if self.parent.instance:
            #Field already set, don't allow changes, blocks incomming and set to read-only
            existing_value = getattr(self.parent.instance, self.field_name, None)
            if existing_value  is not None and data != existing_value:
                raise serializers.ValidationError(
                    f"This field cannot be changed once set"
                )
        return super().validate_empty_values(data)


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)
    # Todo implmeant an account activation process where a code will b sent to users email the are to enter the code givivng to them to complete ther signup process. Use signals to send the code to the users on signup.

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "email",
            "password",
            "password2",
        ]

    def validate(self, attrs):
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if password != password2:
            raise serializers.ValidationError({"passwords do not match"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)

        user = CustomUser.objects.create_user(**validated_data)
        return user

class UserBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "display_name",
            "email",
            "first_name",
            "last_name"
        ]
        read_only_fields = ["id","username", "email"]

class UserProfileSerializer(serializers.ModelSerializer):
    user = UserBasicSerializer(required=False)
    user_first_name = serializers.CharField(required=False, write_only=True)
    user_last_name = serializers.CharField(required=False, write_only=True)
    user_display_name = serializers.CharField(required=False, write_only=True)

    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True
    )
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
        read_only_fields = ["created_at","updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make DOB read only if it's already set
        if self.instance and self.instance.date_of_birth:
            self.fields['date_of_birth'].read_only=True
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
            changed = [f for f in ("first_name", "last_name", "display_name") if f in user_data]
            if changed:
                u.save(update_fields=changed)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class EmailChangeSerializer(serializers.Serializer):
    """Allow email change with password verification"""
    new_email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value
    def validate(self, attrs):
        user = self.context['request'].user
        if not user.check_password(attrs['password']):
            raise serializers.ValidationError({"password":"Incorrect password"})
        return attrs
        
    def save(self):
        user = self.context['request'].user
        user.email = self.validated_data['new_email']
        user.save(update_fields=['email'])
        return user
class PassowrdChangeSerializer(serializers.Serializer):
    """Allow password change with old password verification"""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    new_password2 = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError({"password":"Incorrect password"})
        return value
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password2":"Passwords do not match."})
        attrs.pop('new_password2', None)
        return attrs
        
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
    
class PasswordResetRequestSerializer(serializers.Serializer):
    """Request password reset via email"""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Check if email exist(do not reveal to users for security)"""
        # Validate but don't raise error if not found
        return value.lower()
    
    def save(self):
        email = self.validated_data['email']
        # Try to find user
        try:
            user = CustomUser.objects.get(email=email)

            # Generate token 
            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)

            #Encode user ID 

            uid = urlsafe_base64_encode(force_bytes(user.pk))

            #Build reset url
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
            # Send email
            subject = "Reset Your Password"
            message = f"""Hi {user.username}, 
            You requested to rest your password. Click the link below: {reset_url}
            This link expires in 60 minutes. 
            If you didn't request this, please ignore this email.
            Best regards, 
            Mini E-com Team"""

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
        except CustomUser.DoesNotExist:
                # Don't reveal that the email dose not exist(security)
                pass
                
        # Always return success
        return {"detail":"If email exists, a reset link has been sent."}
    
class PasswordRestConfirmSerializer(serializers.Serializer):
    """Confirm password reset with token"""
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True,required=True, min_length=8)
    new_password2 = serializers.CharField(write_only=True,required=True)

    def validate(self, attrs):
        # Check if password match
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password2":"Passwords do not match."})
        
        # Decode uid and get user
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            user = CustomUser.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            raise serializers.ValidationError({"uid":"Invalid reset link."})
        
        # Verify token 
        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token":"Invalid or expired reset link"})
        
        # Store user for save method
        attrs['user'] = user
        return attrs
    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()

        # Delete old auth token and create new one

        try: 
            user.auth_token.delete()
        except:
            pass
        return user