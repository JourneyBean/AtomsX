"""
User model for AtomsX Visual Coding Platform.

Custom User model that integrates with OIDC authentication.
Uses OIDC 'sub' (subject) as the unique identifier from the identity provider.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """
    Custom user manager for OIDC-based authentication.
    """

    def create_user(self, oidc_sub, email, display_name=None, **extra_fields):
        """
        Create a user from OIDC information.
        """
        if not oidc_sub:
            raise ValueError('OIDC sub is required')
        if not email:
            raise ValueError('Email is required')

        user = self.model(
            oidc_sub=oidc_sub,
            email=self.normalize_email(email),
            display_name=display_name or email.split('@')[0],
            **extra_fields,
        )
        user.save(using=self._db)
        return user

    def create_superuser(self, oidc_sub, email, display_name=None, **extra_fields):
        """
        Create a superuser (for admin access).
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(oidc_sub, email, display_name, **extra_fields)

    def get_or_create_from_oidc(self, oidc_sub: str, email: str, display_name: str = None):
        """
        Get an existing user or create a new one from OIDC info.
        """
        try:
            user = self.get(oidc_sub=oidc_sub)
            # Update email/display_name if changed
            if user.email != email:
                user.email = email
            if display_name and user.display_name != display_name:
                user.display_name = display_name
            user.save(update_fields=['email', 'display_name'])
            return user, False
        except self.model.DoesNotExist:
            return self.create_user(oidc_sub, email, display_name), True


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for OIDC authentication.

    Primary identifier is the OIDC 'sub' (subject claim) from the identity provider.
    This ensures unique identification across different providers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    oidc_sub = models.CharField(
        max_length=255,
        unique=True,
        help_text='OIDC subject identifier from the identity provider',
    )
    email = models.EmailField(unique=True, help_text='Email from OIDC provider')
    display_name = models.CharField(max_length=255, help_text='Display name from OIDC provider')

    # Required for Django admin
    is_staff = models.BooleanField(default=False, help_text='Can access Django admin')
    is_active = models.BooleanField(default=True, help_text='User is active')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'oidc_sub'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['oidc_sub']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f'{self.display_name} ({self.email})'

    def get_short_name(self):
        return self.display_name

    def natural_key(self):
        return (self.oidc_sub,)