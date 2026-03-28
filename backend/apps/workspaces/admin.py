from django.contrib import admin
from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    """
    Admin interface for Workspace model.
    """

    list_display = ('id', 'name', 'owner', 'status', 'container_id', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'owner__email', 'container_id')
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'owner', 'name'),
        }),
        ('Container', {
            'fields': ('container_id', 'container_host', 'status', 'error_message'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )