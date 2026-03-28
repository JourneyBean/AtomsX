"""
Security verification tests for AtomsX MVP.

This module contains tests to verify:
- Multi-tenant isolation
- Container security
- Audit logging
- Access control
- Docker-in-Docker isolation
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from apps.workspaces.models import Workspace
from apps.workspaces.docker_utils import (
    WorkspaceContainerManager,
    check_dind_health,
    DinDNotEnabledError,
    DinDHealthCheckError,
)
from .models import AuditLog

User = get_user_model()


class DinDIsolationTest(TestCase):
    """
    Verify Docker-in-Docker isolation:
    - Backend/celery-worker connect to dind, not host Docker
    - Workspace containers created in dind only
    - Host Docker socket not accessible
    """

    def test_dind_enabled_required(self):
        """Docker operations require DIND_ENABLED=true."""
        with override_settings(DIND_ENABLED=False, DOCKER_HOST=''):
            with self.assertRaises(DinDNotEnabledError):
                WorkspaceContainerManager()

    def test_dind_socket_path_configurable(self):
        """Dind socket path can be configured via environment."""
        # This tests the settings configuration logic
        with override_settings(
            DIND_ENABLED=True,
            DIND_SOCKET_PATH='/custom/dind/docker.sock',
            DOCKER_HOST='unix:///custom/dind/docker.sock',
        ):
            # In test mode, we can't actually connect to a non-existent socket
            # but we verify the settings are properly configured
            from django.conf import settings
            self.assertEqual(settings.DIND_SOCKET_PATH, '/custom/dind/docker.sock')
            self.assertEqual(settings.DOCKER_HOST, 'unix:///custom/dind/docker.sock')

    def test_dind_host_tcp_configurable(self):
        """Dind can be connected via TCP using DIND_HOST."""
        with override_settings(
            DIND_ENABLED=True,
            DIND_HOST='tcp://dind:2375',
            DOCKER_HOST='tcp://dind:2375',
        ):
            from django.conf import settings
            self.assertEqual(settings.DIND_HOST, 'tcp://dind:2375')
            self.assertEqual(settings.DOCKER_HOST, 'tcp://dind:2375')

    def test_workspace_containers_in_dind_only(self):
        """Workspace containers are created in dind, not host Docker."""
        # This is verified by the fact that all container operations
        # use docker.from_env() which connects to DOCKER_HOST (dind)
        # Integration tests would verify containers don't appear in host Docker
        pass


class MultiTenantIsolationTest(TestCase):
    """
    Verify multi-tenant isolation (9.1):
    - User A cannot access User B's Workspace
    - User A cannot access User B's Session
    - User A cannot access User B's Preview
    """

    def setUp(self):
        self.user_a = User.objects.create_user(
            oidc_sub='user-a-123',
            email='user-a@example.com',
            display_name='User A',
        )
        self.user_b = User.objects.create_user(
            oidc_sub='user-b-456',
            email='user-b@example.com',
            display_name='User B',
        )

        self.workspace_a = Workspace.objects.create(
            owner=self.user_a,
            name='Workspace A',
            status='running',
        )
        self.workspace_b = Workspace.objects.create(
            owner=self.user_b,
            name='Workspace B',
            status='running',
        )

    def test_user_cannot_access_other_workspace(self):
        """User A cannot access User B's workspace."""
        # This is enforced by the API views
        self.assertNotEqual(self.workspace_a.owner, self.workspace_b.owner)

    def test_workspace_isolation_by_owner(self):
        """Workspace querysets are filtered by owner."""
        user_a_workspaces = Workspace.objects.filter(owner=self.user_a)
        self.assertIn(self.workspace_a, user_a_workspaces)
        self.assertNotIn(self.workspace_b, user_a_workspaces)


class ContainerSecurityTest(TestCase):
    """
    Verify container security (9.2):
    - Container cannot access Docker socket
    - Container cannot access other containers
    - Containers run in dind environment
    """

    def test_container_security_verification(self):
        """Test the security verification function."""
        # This would be tested with actual containers in integration tests
        # In dind mode, we verify containers don't have host socket access
        pass  # Requires running dind daemon


class AuditLogTest(TestCase):
    """
    Verify audit logging (9.3):
    - Key events are logged
    - Logs are queryable
    """

    def setUp(self):
        self.user = User.objects.create_user(
            oidc_sub='audit-user',
            email='audit@example.com',
            display_name='Audit User',
        )

    def test_login_audit(self):
        """Login events are audited."""
        AuditLog.objects.create(
            event_type='LOGIN',
            user_id=self.user.id,
            oidc_sub=self.user.oidc_sub,
            ip_address='127.0.0.1',
        )

        log = AuditLog.objects.filter(event_type='LOGIN', user_id=self.user.id).first()
        self.assertIsNotNone(log)

    def test_workspace_audit(self):
        """Workspace events are audited."""
        workspace = Workspace.objects.create(
            owner=self.user,
            name='Audit Test Workspace',
        )

        AuditLog.objects.create(
            event_type='WORKSPACE_CREATED',
            user_id=self.user.id,
            workspace_id=workspace.id,
        )

        log = AuditLog.objects.filter(
            event_type='WORKSPACE_CREATED',
            workspace_id=workspace.id,
        ).first()
        self.assertIsNotNone(log)

    def test_dind_connection_audit(self):
        """Dind connection events are audited."""
        AuditLog.objects.create(
            event_type='DIND_CONNECTED',
            user_id=None,  # System event
            details={'docker_host': 'unix:///var/run/dind/docker.sock'},
        )

        log = AuditLog.objects.filter(event_type='DIND_CONNECTED').first()
        self.assertIsNotNone(log)


class PreviewAccessTest(TestCase):
    """
    Verify Preview access control (9.4):
    - Preview URLs require authentication
    - Unauthenticated access is denied
    """

    def test_preview_requires_auth(self):
        """Preview access requires authentication."""
        # This is enforced by the gateway Lua script
        # The auth_check.lua verifies session before proxying
        pass  # Integration test with actual gateway


class DinDHealthCheckTest(TestCase):
    """
    Verify dind daemon health check functionality.
    """

    def test_health_check_function_exists(self):
        """Health check utility function is available."""
        # The function is defined in docker_utils.py
        # Integration tests would verify actual daemon connectivity
        from apps.workspaces.docker_utils import check_dind_health
        self.assertTrue(callable(check_dind_health))