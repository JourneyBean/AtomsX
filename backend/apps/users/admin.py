from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Admin interface for User model.
    """

    list_display = ('id', 'email', 'display_name', 'oidc_sub', 'is_staff', 'created_at')
    list_filter = ('is_staff', 'is_active', 'created_at')
    search_fields = ('email', 'display_name', 'oidc_sub')
    readonly_fields = ('id', 'oidc_sub', 'created_at', 'updated_at')

    fieldsets = (
        ('OIDC Information', {
            'fields': ('oidc_sub', 'email', 'display_name'),
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    ordering = ('-created_at',)