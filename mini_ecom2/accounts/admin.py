from django.contrib import admin
from .models import CustomUser, UserProfile

# Register your models here.


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "first_name", "last_name", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser", "date_joined"]
    list_display_links = ["email", "username"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering = ["-date_joined"]


admin.site.register(UserProfile)
