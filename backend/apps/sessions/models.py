"""
Session model for Agent conversations.

A Session represents a conversation between a user and an AI Agent
within a specific Workspace. Messages are stored as JSON for flexibility.
"""
import uuid
from django.db import models
from django.conf import settings


class Session(models.Model):
    """
    Session model for Agent conversations.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text='Workspace this session is bound to',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text='User who owns this session',
    )
    messages = models.JSONField(
        default=list,
        help_text='List of messages in the conversation',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text='Current status of the session',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sessions'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['workspace']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Session {self.id} ({self.workspace.name})'

    def add_message(self, role: str, content: str, status: str = 'complete'):
        """
        Add a message to the session.
        """
        import uuid
        from datetime import datetime

        message = {
            'id': str(uuid.uuid4()),
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': status,
        }
        self.messages.append(message)
        self.save(update_fields=['messages', 'updated_at'])
        return message

    def update_message_status(self, message_id: str, status: str, content: str = None):
        """
        Update the status of a message.
        """
        for msg in self.messages:
            if msg.get('id') == message_id:
                msg['status'] = status
                if content is not None:
                    msg['content'] = content
                break
        self.save(update_fields=['messages', 'updated_at'])

    async def aadd_message(self, role: str, content: str, status: str = 'complete'):
        """
        Async version of add_message.
        """
        import uuid
        from datetime import datetime
        from asgiref.sync import sync_to_async

        message = {
            'id': str(uuid.uuid4()),
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': status,
        }
        self.messages.append(message)
        await sync_to_async(self.save)(update_fields=['messages', 'updated_at'])
        return message