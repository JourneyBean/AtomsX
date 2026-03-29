"""
Workspace model for AtomsX Visual Coding Platform.

A Workspace is an isolated development environment where users can:
- Interact with an AI Agent
- View real-time previews of their code
- Store source files in an isolated container

Each workspace runs in its own Docker container with:
- Agent Runtime
- Preview Server (Vite Dev Server)
- Source code volume
"""
import secrets
import uuid
from django.db import models
from django.conf import settings


class Workspace(models.Model):
    """
    Workspace model representing an isolated development environment.
    """

    STATUS_CHOICES = [
        ('creating', 'Creating'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('error', 'Error'),
        ('deleting', 'Deleting'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspaces',
        help_text='User who owns this workspace',
    )
    name = models.CharField(
        max_length=100,
        help_text='User-defined name for the workspace',
    )
    container_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text='Docker container ID',
    )
    container_host = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Host:port for the container preview server',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='creating',
        help_text='Current status of the workspace',
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text='Error message if status is error',
    )
    data_dir_path = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text='Host path to user data directory (UUID-sharded structure)',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspaces'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'],
                name='unique_workspace_name_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.name} ({self.owner.display_name})'

    @property
    def preview_url(self):
        """Get the preview URL for this workspace."""
        if self.status == 'running':
            return f'http://{self.id}.{settings.ATOMSX_PREVIEW_DOMAIN}'
        return None

    @property
    def deploy_url(self):
        """Get the deployed app URL for this workspace."""
        if self.status == 'running':
            return f'http://{self.id}.{settings.ATOMSX_DEPLOY_DOMAIN}'
        return None

    def transition_status(self, new_status: str, error_message: str = None):
        """
        Transition workspace to a new status with validation.
        """
        valid_transitions = {
            'creating': ['running', 'error'],
            'running': ['stopped', 'error', 'deleting'],
            'stopped': ['running', 'deleting'],
            'error': ['creating', 'deleting'],
            'deleting': [],  # Terminal state
        }

        if new_status not in valid_transitions.get(self.status, []):
            raise ValueError(f'Invalid status transition from {self.status} to {new_status}')

        self.status = new_status
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])


class WorkspaceToken(models.Model):
    """
    Authentication token for Workspace Client WebSocket connections.

    Tokens are generated when a workspace container is created and
    deleted when the container is stopped or deleted.

    Security:
    - Token is only injected into the container environment
    - Token is never logged or exposed in API responses
    - Token is bound to a specific workspace (cannot be used for other workspaces)
    """

    workspace = models.OneToOneField(
        Workspace,
        on_delete=models.CASCADE,
        related_name='auth_token',
        help_text='Workspace this token authenticates',
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text='URL-safe token string',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workspace_tokens'

    def __str__(self):
        return f'Token for {self.workspace.name}'

    @classmethod
    def generate_token(cls) -> str:
        """
        Generate a secure random token.

        Uses secrets.token_urlsafe for cryptographically secure
        random tokens suitable for authentication.
        """
        return secrets.token_urlsafe(32)

    @classmethod
    def create_for_workspace(cls, workspace: Workspace) -> 'WorkspaceToken':
        """
        Create a new token for a workspace.

        Ensures token uniqueness by regenerating on collision.
        """
        token = cls.generate_token()
        # Ensure uniqueness (very unlikely collision, but handle it)
        while cls.objects.filter(token=token).exists():
            token = cls.generate_token()

        return cls.objects.create(workspace=workspace, token=token)