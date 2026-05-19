from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "status", "source", "entity_type", "entity_id", "created_at")
    list_filter = ("event_type", "status", "channel", "source")
    search_fields = ("message", "entity_id", "source")
    autocomplete_fields = ("actor",)
