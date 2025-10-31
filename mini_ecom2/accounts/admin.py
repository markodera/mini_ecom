from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserProfile

# Register your models here.


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "display_name",
        "is_verified",
        "is_active",
        "date_joined",
    ]
    list_filter = [
        "is_active",
        "is_verified",
        "is_staff",
        "is_superuser",
        "date_joined",
    ]
    list_display_links = ["email", "username"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["-date_joined"]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Personal Info",
            {"fields": ("display_name", "email", "first_name", "last_name")},
        ),
        (
            "Verification & Permissions",
            {
                "fields": (
                    "is_verified",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )
    #   Fieldsets when add a new user
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "password1",
                    "password2",
                    "is_verified",
                    "is_active",
                ),
            },
        ),
    )
    inlines = [UserProfileInline]


@admin.register(UserProfile)
class CustomAdminProfile(admin.ModelAdmin):
    list_display = [
        "user",
        "get_email",
        "get_verified_status",
        "gender",
        "date_of_birth",
        "profile_picture_preview",
        "created_at",
    ]
    list_filter = ["gender", "created_at", "user__is_verified"]
    search_fields = ["user__username", "user__email", "bio"]
    readonly_fields = ["created_at", "updated_at", "profile_picture_preview"]
    ordering = ["-created_at"]

    fieldsets = (
        ("User Info", {"fields": ("user",)}),
        (
            "Profile Details",
            {"fields": ("bio", "profile_picture", "gender", "date_of_birth")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse")},
        ),
    )

    def get_email(self, obj):
        """Display user email"""
        return obj.user.email

    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def get_verified_status(self, obj):
        """Display verification status"""
        if obj.user.is_verified:
            return "Verified"
        return "Not verified"

    get_verified_status.short_description = "Verfication"
    get_verified_status.admin_order_field = "user__is_verified"

    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius: 5px;" />',
                obj.profile_picture.url,
            )
        return "No image"

    profile_picture_preview.allow_tags = True
