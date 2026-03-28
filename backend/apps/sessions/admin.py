from django.contrib import admin
from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    """
    Admin interface for Session model.
    """

    list_display = ('id', 'workspace', 'user', 'status', 'message_count', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'workspace__name', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at')

    def message_count(self, obj):
        return len(obj.messages)

    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'workspace', 'user', 'status'),
        }),
        ('Messages', {
            'fields': ('messages',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )