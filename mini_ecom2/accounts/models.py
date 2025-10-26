from PIL import Image
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError

from rest_framework.authtoken.models import Token

# Create your models here.
def validate_not_future_date(value):
    if value and value > timezone.now().date():
        raise ValidationError("Date of birth cannot be in the future.")

GENDER = [("male", "Male"), ("female", "Female"), ("rather_not_say", "Rather not say")]


class CustomUser(AbstractUser):
    email = models.EmailField(max_length=225, unique=True, null=False, blank=False)
    display_name = models.CharField(max_length=225, blank=True, null= True, help_text="This will be your name others will know you as.")
    """This is to validate that users used a real enail when signing up"""
    # email_verified = models.BooleanField("Email verified",default=False, help_text="Whether the user's email has been verified")
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to="profile_picture/", blank=True, null=True
    )
    gender = models.CharField(max_length=20, choices=GENDER, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True, validators=[validate_not_future_date])
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
