from PIL import Image
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from phonenumber_field.modelfields import PhoneNumberField
from rest_framework.authtoken.models import Token


# Create your models here.
def validate_not_future_date(value):
    if value and value > timezone.now().date():
        raise ValidationError("Date of birth cannot be in the future.")


GENDER = [("male", "Male"), ("female", "Female"), ("rather_not_say", "Rather not say")]


class CustomUser(AbstractUser):
    email = models.EmailField(max_length=225, unique=True, null=False, blank=False)
    phone_number = PhoneNumberField(blank=True, null=True, unique=True)
    phone_number_verified = models.BooleanField(
        default=False, help_text="Has this phone number has been verified via SMS?"
    )
    display_name = models.CharField(
        max_length=225,
        blank=True,
        null=True,
        help_text="Thie name others will know you as.",
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return str(self.display_name or self.get_full_name() or self.email)


class UserProfile(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="profile"
    )
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to="profile_picture/", blank=True, null=True
    )
    gender = models.CharField(max_length=20, choices=GENDER, blank=True, null=True)
    date_of_birth = models.DateField(
        blank=True, null=True, validators=[validate_not_future_date]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.profile_picture and hasattr(self.profile_picture, "path"):
            img = Image.open(self.profile_picture.path)
            img.thumbnail((512, 512))
            img.save(self.profile_picture.path, optimize=True, quality=85)

    def __str__(self):
        return f"{self.user.username}'s profile"


class PhoneVerification(models.Model):
    """ "
    Store phone verification codes"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_verifications",
    )
    phone_number = PhoneNumberField()
    verification_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        help_text="Code expires in 10 minutes after creation"
    )
    attempts = models.PositiveIntegerField(
        default=0, help_text="Failed verification attempts for this code (Max 5)"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "verified_at"]),
            models.Index(fields=["user", "created_at"]),
        ]
        verbose_name = "Phone Verification"
        verbose_name_plural = "Phone Verifications"

    def __str__(self):
        status = "verified" if self.verified_at else "pending"
        return f"{self.phone_number} - {status}"

    def is_expired(self):
        from django.utils import timezone

        return timezone.now() > self.expires_at

    def is_valid(self):
        """Allow max 5 verification attempts"""
        return not self.is_expired() and not self.verified_at and self.attempts < 5

    def can_request_new_code(self):
        return self.is_expired() or self.attempts >= 5 or self.verified_at

    def increment_attempts(self):
        self.attempts += 1
        self.save(update_fields=["attempts"])

    def mark_verified(self):
        from django.utils import timezone

        if self.verified_at:
            return

        self.verified_at = timezone.now()
        self.save(update_fields=["verified_at"])

        # Update user's verification status
        self.user.phone_number = self.phone_number
        self.user.phone_number_verified = True
        self.user.save(update_fields=["phone_number", "phone_number_verified"])
