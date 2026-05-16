from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("SubasTech", {"fields": ("role", "phone_number", "whatsapp_id")}),)
    list_display = ("username", "email", "role", "phone_number", "is_active")
    list_filter = UserAdmin.list_filter + ("role",)
