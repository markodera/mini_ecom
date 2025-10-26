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
    list_display = ["username", "email", "first_name", "last_name", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser", "date_joined"]
    list_display_links = ["email", "username"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["-date_joined"]
    inlines = [UserProfileInline]


@admin.register(UserProfile)
class CustomAdminProfile(admin.ModelAdmin):
    list_display = ["user", "gender", "date_of_birth","profile_picture_preview", "created_at"]
    list_filter = ["gender", "created_at", ]
    search_fields = ["user__username", "user__email", "bio"]
    readonly_fields = ["created_at", "updated_at", "profile_picture_preview"]
    ordering = ["-created_at"]
    
    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 5px;" />', obj.profile_picture.url)
        return "No image"
    profile_picture_preview.allow_tags = True

