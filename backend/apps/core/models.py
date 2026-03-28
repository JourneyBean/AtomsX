"""
Core models - AuditLog and shared utilities.
"""
from django.db import models


class AuditLog(models.Model):
    """
    Audit log for tracking key events in the platform.
    """
    EVENT_TYPES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('WORKSPACE_CREATED', 'Workspace Created'),
        ('WORKSPACE_DELETED', 'Workspace Deleted'),
        ('WORKSPACE_STATUS_CHANGE', 'Workspace Status Change'),
        ('WORKSPACE_ERROR', 'Workspace Error'),
        ('PREVIEW_ACCESS', 'Preview Access'),
        ('PREVIEW_ACCESS_DENIED', 'Preview Access Denied'),
        ('FILE_MODIFIED', 'File Modified'),
        ('MESSAGE_SENT', 'Message Sent'),
        ('AGENT_RESPONSE', 'Agent Response'),
        # Docker-in-Docker events
        ('DIND_CONNECTED', 'Dind Connected'),
        ('DIND_DISCONNECTED', 'Dind Disconnected'),
        ('DIND_HEALTH_CHECK_FAILED', 'Dind Health Check Failed'),
        ('DIND_ERROR', 'Dind Error'),
    ]

    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_id = models.UUIDField(null=True, blank=True, help_text='Reference to user who triggered the event')
    oidc_sub = models.CharField(max_length=255, null=True, blank=True, help_text='OIDC subject identifier')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    workspace_id = models.UUIDField(null=True, blank=True)
    session_id = models.UUIDField(null=True, blank=True)
    container_id = models.CharField(max_length=64, null=True, blank=True)
    previous_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20, null=True, blank=True)
    file_path = models.CharField(max_length=500, null=True, blank=True)
    operation = models.CharField(max_length=20, null=True, blank=True, help_text='create/modify/delete')
    message_role = models.CharField(max_length=10, null=True, blank=True, help_text='user/agent')
    message_summary = models.TextField(null=True, blank=True, help_text='Truncated message content')
    error_message = models.TextField(null=True, blank=True)
    reason = models.CharField(max_length=100, null=True, blank=True, help_text='Reason for denial/error')
    details = models.JSONField(default=dict, blank=True, help_text='Additional event details (e.g., dind connection info)')
    metadata = models.JSONField(default=dict, blank=True, help_text='Additional event metadata')

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['workspace_id']),
        ]

    def __str__(self):
        return f'{self.event_type} at {self.timestamp}'


def create_audit_log(event_type, **kwargs):
    """
    Helper function to create an audit log entry.
    """
    return AuditLog.objects.create(event_type=event_type, **kwargs)