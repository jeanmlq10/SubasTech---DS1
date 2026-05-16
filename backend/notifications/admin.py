from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "channel", "title", "is_read", "created_at")
    list_filter = ("channel", "is_read", "created_at")
    search_fields = ("user__username", "title", "message")
