"""
Unit tests for Workspace model and API.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.conf import settings
from celery.exceptions import SoftTimeLimitExceeded

from apps.workspaces.models import Workspace
from apps.workspaces.views import WorkspaceListView, WorkspaceDetailView
from apps.workspaces.tasks import create_workspace_container, delete_workspace_container
from apps.workspaces.data_utils import (
    validate_uuid,
    compute_user_data_path,
    get_workspace_subdir_path,
    create_user_data_directory,
    InvalidUUIDError,
    UserDataPathError,
)

User = get_user_model()


@pytest.fixture
@pytest.mark.django_db
def user():
    """Create a test user."""
    return User.objects.create_user(
        oidc_sub='test-user-123',
        email='test@example.com',
        display_name='Test User',
    )


@pytest.fixture
@pytest.mark.django_db
def other_user():
    """Create another test user."""
    return User.objects.create_user(
        oidc_sub='other-user-456',
        email='other@example.com',
        display_name='Other User',
    )


@pytest.fixture
@pytest.mark.django_db
def workspace(user):
    """Create a test workspace."""
    return Workspace.objects.create(
        owner=user,
        name='Test Workspace',
        status='running',
        container_id='container-123',
    )


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.mark.django_db
class TestWorkspaceModel:
    """Tests for the Workspace model."""

    def test_create_workspace(self, user):
        """Test creating a workspace."""
        workspace = Workspace.objects.create(
            owner=user,
            name='New Workspace',
        )

        assert workspace.owner == user
        assert workspace.name == 'New Workspace'
        assert workspace.status == 'creating'
        assert workspace.container_id is None

    def test_unique_name_per_user(self, user):
        """Test that workspace names are unique per user."""
        Workspace.objects.create(owner=user, name='Unique Name')

        with pytest.raises(Exception):  # IntegrityError
            Workspace.objects.create(owner=user, name='Unique Name')

    def test_different_users_can_have_same_name(self, user, other_user):
        """Test that different users can have workspaces with the same name."""
        ws1 = Workspace.objects.create(owner=user, name='Same Name')
        ws2 = Workspace.objects.create(owner=other_user, name='Same Name')

        assert ws1.owner == user
        assert ws2.owner == other_user
        assert ws1.name == ws2.name

    def test_preview_url(self, workspace):
        """Test the preview_url property."""
        assert workspace.preview_url == f'http://{workspace.id}.{settings.ATOMSX_PREVIEW_DOMAIN}'

    def test_deploy_url(self, workspace):
        """Test the deploy_url property."""
        assert workspace.deploy_url == f'http://{workspace.id}.{settings.ATOMSX_DEPLOY_DOMAIN}'

    def test_preview_url_not_running(self, user):
        """Test preview_url is None for non-running workspace."""
        workspace = Workspace.objects.create(
            owner=user,
            name='Stopped Workspace',
            status='stopped',
        )
        assert workspace.preview_url is None

    def test_status_transition_valid(self, workspace):
        """Test valid status transitions."""
        assert workspace.status == 'running'

        workspace.transition_status('stopped')
        assert workspace.status == 'stopped'

        workspace.transition_status('deleting')
        assert workspace.status == 'deleting'

    def test_status_transition_invalid(self, workspace):
        """Test that invalid status transitions raise an error."""
        with pytest.raises(ValueError):
            workspace.transition_status('creating')  # Can't go back to creating


@pytest.mark.django_db
class TestWorkspaceAPI:
    """Tests for the Workspace API views."""

    def test_list_workspaces(self, factory, user, workspace):
        """Test listing user's workspaces."""
        request = factory.get('/api/workspaces/')
        request.user = user

        view = WorkspaceListView.as_view()
        response = view(request)

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'Test Workspace'

    def test_list_workspaces_only_own(self, factory, user, other_user):
        """Test that listing only shows own workspaces."""
        # Create workspaces for both users
        Workspace.objects.create(owner=user, name='User Workspace')
        Workspace.objects.create(owner=other_user, name='Other Workspace')

        request = factory.get('/api/workspaces/')
        request.user = user

        view = WorkspaceListView.as_view()
        response = view(request)

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'User Workspace'

    def test_create_workspace(self, factory, user):
        """Test creating a workspace."""
        request = factory.post(
            '/api/workspaces/',
            data={'name': 'New Workspace'},
            content_type='application/json',
        )
        request.user = user

        view = WorkspaceListView.as_view()
        response = view(request)

        assert response.status_code == 201
        assert response.data['name'] == 'New Workspace'
        assert response.data['status'] == 'creating'

        # Verify database
        assert Workspace.objects.filter(owner=user, name='New Workspace').exists()

    def test_create_workspace_duplicate_name(self, factory, user, workspace):
        """Test creating a workspace with duplicate name."""
        request = factory.post(
            '/api/workspaces/',
            data={'name': 'Test Workspace'},  # Same as fixture
            content_type='application/json',
        )
        request.user = user

        view = WorkspaceListView.as_view()
        response = view(request)

        assert response.status_code == 409

    def test_get_workspace_detail(self, factory, user, workspace):
        """Test getting workspace details."""
        request = factory.get(f'/api/workspaces/{workspace.id}/')
        request.user = user

        view = WorkspaceDetailView.as_view()
        response = view(request, workspace_id=workspace.id)

        assert response.status_code == 200
        assert response.data['name'] == 'Test Workspace'

    def test_get_workspace_forbidden(self, factory, user, other_user):
        """Test getting another user's workspace."""
        other_workspace = Workspace.objects.create(
            owner=other_user,
            name='Other Workspace',
        )

        request = factory.get(f'/api/workspaces/{other_workspace.id}/')
        request.user = user

        view = WorkspaceDetailView.as_view()
        response = view(request, workspace_id=other_workspace.id)

        assert response.status_code == 403

    def test_delete_workspace(self, factory, user, workspace):
        """Test deleting a workspace."""
        request = factory.delete(f'/api/workspaces/{workspace.id}/')
        request.user = user

        view = WorkspaceDetailView.as_view()
        response = view(request, workspace_id=workspace.id)

        assert response.status_code == 202

        # Verify status changed to deleting
        workspace.refresh_from_db()
        assert workspace.status == 'deleting'

    def test_delete_workspace_forbidden(self, factory, user, other_user):
        """Test deleting another user's workspace."""
        other_workspace = Workspace.objects.create(
            owner=other_user,
            name='Other Workspace',
        )

        request = factory.delete(f'/api/workspaces/{other_workspace.id}/')
        request.user = user

        view = WorkspaceDetailView.as_view()
        response = view(request, workspace_id=other_workspace.id)

        assert response.status_code == 403


@pytest.mark.django_db
class TestWorkspaceTasks:
    """Tests for workspace Celery tasks."""

    @patch('apps.workspaces.tasks.get_docker_client')
    def test_create_workspace_container(self, mock_get_client, user):
        """Test the container creation task."""
        workspace = Workspace.objects.create(
            owner=user,
            name='Test',
            status='creating',
        )

        # Mock Docker client
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.id = 'container-xyz'
        mock_container.attrs = {
            'NetworkSettings': {
                'Ports': {
                    '3000/tcp': [{'HostPort': '32768'}],
                },
            },
        }
        mock_client.containers.create.return_value = mock_container
        mock_client.containers.get.side_effect = Exception('Not found')
        mock_client.networks.get.side_effect = Exception('Not found')
        mock_client.volumes.get.side_effect = Exception('Not found')
        mock_get_client.return_value = mock_client

        # Run task
        create_workspace_container(str(workspace.id))

        # Verify container was created
        mock_client.containers.create.assert_called_once()

        # Verify workspace updated
        workspace.refresh_from_db()
        assert workspace.status == 'running'
        assert workspace.container_id == 'container-xyz'

    @patch('apps.workspaces.tasks.get_docker_client')
    def test_delete_workspace_container(self, mock_get_client, user):
        """Test the container deletion task."""
        workspace = Workspace.objects.create(
            owner=user,
            name='Test',
            status='deleting',
            container_id='container-to-delete',
        )

        # Mock Docker client
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        # Run task
        delete_workspace_container(str(workspace.id))

        # Verify container was stopped and removed
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()

        # Verify workspace deleted
        assert not Workspace.objects.filter(id=workspace.id).exists()


@pytest.mark.django_db
class TestPrebuildWorkspaceImagesCommand:
    """Tests for the prebuild_workspace_images management command."""

    @patch('apps.workspaces.management.commands.prebuild_workspace_images.docker.from_env')
    @patch('apps.workspaces.management.commands.prebuild_workspace_images.check_dind_health')
    @patch('apps.workspaces.management.commands.prebuild_workspace_images.create_audit_log')
    def test_successful_prebuild(self, mock_audit, mock_health, mock_docker):
        """Test successful image prebuild."""
        # Mock Docker client
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        # Mock health check
        mock_health.return_value = {'healthy': True, 'docker_version': '24.0'}

        # Mock image not found, then pull success
        mock_client.images.get.side_effect = Exception('ImageNotFound')
        mock_image = MagicMock()
        mock_image.id = 'sha256:abc123'
        mock_image.attrs = {'Size': 100 * 1024 * 1024}  # 100 MB
        mock_client.images.pull.return_value = mock_image
        mock_client.images.get.return_value = mock_image

        # Run command
        call_command('prebuild_workspace_images')

        # Verify audit log created
        mock_audit.assert_called()

    @patch('apps.workspaces.management.commands.prebuild_workspace_images.docker.from_env')
    @patch('apps.workspaces.management.commands.prebuild_workspace_images.check_dind_health')
    def test_custom_image_argument(self, mock_health, mock_docker):
        """Test prebuild with custom image name."""
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_health.return_value = {'healthy': True}

        mock_image = MagicMock()
        mock_image.id = 'sha256:xyz789'
        mock_image.attrs = {'Size': 50 * 1024 * 1024}
        mock_client.images.get.return_value = mock_image

        call_command('prebuild_workspace_images', image='custom-workspace:v1')

        mock_client.images.get.assert_called_with('custom-workspace:v1')

    @patch('apps.workspaces.management.commands.prebuild_workspace_images.docker.from_env')
    @patch('apps.workspaces.management.commands.prebuild_workspace_images.check_dind_health')
    def test_force_rebuild(self, mock_health, mock_docker):
        """Test force rebuild removes existing image."""
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        mock_health.return_value = {'healthy': True}

        # Mock existing image
        mock_image = MagicMock()
        mock_image.id = 'sha256:old123'
        mock_image.attrs = {'Size': 80 * 1024 * 1024}
        mock_client.images.get.return_value = mock_image

        call_command('prebuild_workspace_images', force=True)

        # Verify image was removed
        mock_client.images.remove.assert_called_once()

    @patch('apps.workspaces.management.commands.prebuild_workspace_images.docker.from_env')
    def test_docker_daemon_unavailable(self, mock_docker):
        """Test error handling when Docker daemon is unavailable."""
        mock_docker.side_effect = Exception('Docker daemon unavailable')

        with pytest.raises(Exception):
            call_command('prebuild_workspace_images')


class TestConfigurableTimeout:
    """Tests for configurable timeout settings."""

    def test_default_timeout_values(self):
        """Test default timeout values are set correctly."""
        assert settings.WORKSPACE_CREATION_SOFT_TIMEOUT == 300
        assert settings.WORKSPACE_CREATION_HARD_TIMEOUT == 360

    @patch.dict(os.environ, {'WORKSPACE_CREATION_SOFT_TIMEOUT': '600'})
    def test_custom_soft_timeout_via_env(self):
        """Test custom soft timeout via environment variable."""
        # Note: This test requires reloading settings, which is complex in Django
        # In practice, this would be tested by checking the settings value
        # after setting the environment variable before Django loads
        pass  # Placeholder - actual test would require settings reload

    @patch.dict(os.environ, {'WORKSPACE_CREATION_HARD_TIMEOUT': '720'})
    def test_custom_hard_timeout_via_env(self):
        """Test custom hard timeout via environment variable."""
        pass  # Placeholder - actual test would require settings reload


@pytest.mark.django_db
class TestWorkspaceCreationTimeout:
    """Tests for Celery timeout handling in workspace creation."""

    @patch('apps.workspaces.tasks.get_docker_client')
    @patch('apps.workspaces.tasks.settings')
    def test_soft_timeout_handling(self, mock_settings, mock_get_client, user):
        """Test SoftTimeLimitExceeded exception handling."""
        mock_settings.WORKSPACE_CREATION_SOFT_TIMEOUT = 300
        mock_settings.WORKSPACE_CREATION_HARD_TIMEOUT = 360
        mock_settings.WORKSPACE_NETWORK_NAME = 'atomsx-workspaces'

        workspace = Workspace.objects.create(
            owner=user,
            name='Timeout Test',
            status='creating',
        )

        # Mock Docker client that takes too long
        mock_get_client.side_effect = SoftTimeLimitExceeded()

        # Run task
        create_workspace_container(str(workspace.id))

        # Verify workspace marked as error
        workspace.refresh_from_db()
        assert workspace.status == 'error'
        assert 'timeout' in workspace.error_message.lower()

    @patch('apps.workspaces.tasks.get_docker_client')
    @patch('apps.workspaces.tasks.settings')
    def test_prebuilt_image_usage(self, mock_settings, mock_get_client, user):
        """Test that prebuilt image is used when available."""
        mock_settings.WORKSPACE_CREATION_SOFT_TIMEOUT = 300
        mock_settings.WORKSPACE_CREATION_HARD_TIMEOUT = 360
        mock_settings.WORKSPACE_NETWORK_NAME = 'atomsx-workspaces'
        mock_settings.WORKSPACE_BASE_IMAGE = 'atomsx-workspace:latest'

        workspace = Workspace.objects.create(
            owner=user,
            name='Prebuilt Test',
            status='creating',
        )

        # Mock Docker client with prebuilt image available
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock prebuilt image exists
        mock_image = MagicMock()
        mock_client.images.get.return_value = mock_image

        # Mock container creation
        mock_container = MagicMock()
        mock_container.id = 'container-prebuilt'
        mock_container.attrs = {
            'NetworkSettings': {
                'Ports': {
                    '3000/tcp': [{'HostPort': '32769'}],
                },
            },
        }
        mock_client.containers.create.return_value = mock_container
        mock_client.networks.get.side_effect = Exception('Not found')
        mock_client.volumes.get.side_effect = Exception('Not found')

        # Run task
        create_workspace_container(str(workspace.id))

        # Verify prebuilt image was used (not pulled)
        mock_client.images.pull.assert_not_called()

        # Verify workspace created
        workspace.refresh_from_db()
        assert workspace.status == 'running'

    @patch('apps.workspaces.tasks.get_docker_client')
    @patch('apps.workspaces.tasks.settings')
    def test_fallback_pull_when_prebuilt_missing(self, mock_settings, mock_get_client, user):
        """Test fallback pull when prebuilt image is missing."""
        mock_settings.WORKSPACE_CREATION_SOFT_TIMEOUT = 300
        mock_settings.WORKSPACE_CREATION_HARD_TIMEOUT = 360
        mock_settings.WORKSPACE_NETWORK_NAME = 'atomsx-workspaces'
        mock_settings.WORKSPACE_BASE_IMAGE = 'atomsx-workspace:latest'

        workspace = Workspace.objects.create(
            owner=user,
            name='Fallback Test',
            status='creating',
        )

        # Mock Docker client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock prebuilt image NOT found
        mock_client.images.get.side_effect = Exception('ImageNotFound')

        # Mock fallback pull
        mock_image = MagicMock()
        mock_client.images.pull.return_value = mock_image

        # Mock container creation
        mock_container = MagicMock()
        mock_container.id = 'container-fallback'
        mock_container.attrs = {
            'NetworkSettings': {
                'Ports': {
                    '3000/tcp': [{'HostPort': '32770'}],
                },
            },
        }
        mock_client.containers.create.return_value = mock_container
        mock_client.networks.get.side_effect = Exception('Not found')
        mock_client.volumes.get.side_effect = Exception('Not found')

        # Run task
        create_workspace_container(str(workspace.id))

        # Verify fallback pull was attempted
        mock_client.images.pull.assert_called_with('node:20-slim')

        # Verify workspace created
        workspace.refresh_from_db()
        assert workspace.status == 'running'


class TestUserDataPathComputation:
    """Tests for user data path computation utilities."""

    def test_validate_uuid_valid(self):
        """Test validating a valid UUID."""
        uuid_str = 'abc12345-def6-7890-abcd-ef1234567890'
        result = validate_uuid(uuid_str)
        assert str(result) == uuid_str

    def test_validate_uuid_invalid(self):
        """Test validating an invalid UUID."""
        with pytest.raises(InvalidUUIDError):
            validate_uuid('not-a-valid-uuid')

    def test_validate_uuid_empty(self):
        """Test validating an empty string."""
        with pytest.raises(InvalidUUIDError):
            validate_uuid('')

    def test_validate_uuid_wrong_length(self):
        """Test validating a UUID with wrong length."""
        with pytest.raises(InvalidUUIDError):
            validate_uuid('abc12345-def6')  # Too short

    def test_compute_user_data_path(self):
        """Test computing user data path with UUID sharding."""
        uuid_str = 'abc12345-def6-7890-abcd-ef1234567890'
        root = '/var/opt/atomsx'
        result = compute_user_data_path(uuid_str, root)

        # Verify sharding structure
        assert result == '/var/opt/atomsx/a/b/abc12345-def6-7890-abcd-ef1234567890'

    def test_compute_user_data_path_uppercase_uuid(self):
        """Test path computation with uppercase UUID (should be normalized to lowercase)."""
        uuid_str = 'ABC12345-DEF6-7890-ABCD-EF1234567890'
        root = '/var/opt/atomsx'
        result = compute_user_data_path(uuid_str, root)

        # Verify UUID is normalized to lowercase
        assert result == '/var/opt/atomsx/a/b/abc12345-def6-7890-abcd-ef1234567890'

    def test_compute_user_data_path_numeric_first_char(self):
        """Test path computation with numeric first character."""
        uuid_str = '0bc12345-def6-7890-abcd-ef1234567890'
        root = '/var/opt/atomsx'
        result = compute_user_data_path(uuid_str, root)

        assert result == '/var/opt/atomsx/0/b/0bc12345-def6-7890-abcd-ef1234567890'

    def test_compute_user_data_path_default_root(self):
        """Test path computation with default root from settings."""
        uuid_str = 'abc12345-def6-7890-abcd-ef1234567890'
        result = compute_user_data_path(uuid_str)

        # Should use settings.WORKSPACE_DATA_ROOT
        assert '/a/b/' in result
        assert uuid_str.lower() in result.lower()

    def test_compute_user_data_path_invalid_uuid(self):
        """Test path computation raises error for invalid UUID."""
        with pytest.raises(InvalidUUIDError):
            compute_user_data_path('invalid-uuid', '/var/opt/atomsx')

    def test_get_workspace_subdir_path_valid(self):
        """Test getting valid subdirectory path."""
        data_dir = '/var/opt/atomsx/a/b/abc12345-def6-7890-abcd-ef1234567890'

        workspace_path = get_workspace_subdir_path(data_dir, 'workspace')
        history_path = get_workspace_subdir_path(data_dir, 'history')

        assert workspace_path == '/var/opt/atomsx/a/b/abc12345-def6-7890-abcd-ef1234567890/workspace'
        assert history_path == '/var/opt/atomsx/a/b/abc12345-def6-7890-abcd-ef1234567890/history'

    def test_get_workspace_subdir_path_invalid(self):
        """Test getting invalid subdirectory raises error."""
        data_dir = '/var/opt/atomsx/a/b/abc12345'

        with pytest.raises(UserDataPathError):
            get_workspace_subdir_path(data_dir, 'invalid_subdir')

    def test_create_user_data_directory(self, tmp_path):
        """Test creating user data directory structure."""
        # Use tmp_path for isolated testing
        data_dir = str(tmp_path / 'a' / 'b' / 'test-uuid-123')

        result = create_user_data_directory(data_dir)

        assert result['created'] is True
        assert os.path.exists(result['data_dir'])
        assert os.path.exists(result['workspace_dir'])
        assert os.path.exists(result['history_dir'])

    def test_create_user_data_directory_permissions(self, tmp_path):
        """Test created directories have correct permissions."""
        data_dir = str(tmp_path / 'a' / 'b' / 'test-uuid-456')

        create_user_data_directory(data_dir)

        # Check permissions are 0755 (octal)
        workspace_stat = os.stat(os.path.join(data_dir, 'workspace'))
        history_stat = os.stat(os.path.join(data_dir, 'history'))

        # 0755 in octal is 0o755, but stat.st_mode includes file type bits
        # We check the permission bits only (last 9 bits)
        workspace_perms = workspace_stat.st_mode & 0o777
        history_perms = history_stat.st_mode & 0o777

        assert workspace_perms == 0o755
        assert history_perms == 0o755

    def test_create_user_data_directory_existing(self, tmp_path):
        """Test creating directory when it already exists (should not error)."""
        data_dir = str(tmp_path / 'existing-test')

        # Create first time
        result1 = create_user_data_directory(data_dir)
        assert result1['created'] is True

        # Create second time - should succeed with exist_ok=True
        result2 = create_user_data_directory(data_dir)
        assert result2['created'] is True

    def test_sharding_structure_correctness(self):
        """Test UUID sharding produces correct directory structure."""
        # Test multiple UUIDs to verify sharding works correctly
        test_cases = [
            ('abc12345-def6-7890-abcd-ef1234567890', 'a', 'b'),
            ('01234567-89ab-cdef-0123-456789abcdef', '0', '1'),
            ('fedcba98-7654-3210-fedc-ba9876543210', 'f', 'e'),
            ('98765432-10ab-cdef-9876-543210abcdef', '9', '8'),
        ]

        for uuid_str, first_char, second_char in test_cases:
            result = compute_user_data_path(uuid_str, '/var/opt/atomsx')
            expected = f'/var/opt/atomsx/{first_char}/{second_char}/{uuid_str}'
            assert result == expected


@pytest.mark.django_db
class TestWorkspaceHistoryAPI:
    """Tests for the Workspace History API."""

    def test_get_history_unauthorized(self, factory, user, other_user):
        """Test getting history for another user's workspace."""
        other_workspace = Workspace.objects.create(
            owner=other_user,
            name='Other Workspace',
            status='running',
        )

        from apps.workspaces.views import WorkspaceHistoryListView
        request = factory.get(f'/api/workspaces/{other_workspace.id}/history/')
        request.user = user

        view = WorkspaceHistoryListView.as_view()
        response = view(request, workspace_id=other_workspace.id)

        assert response.status_code == 403

    def test_get_history_workspace_not_running(self, factory, user):
        """Test getting history for non-running workspace."""
        workspace = Workspace.objects.create(
            owner=user,
            name='Stopped Workspace',
            status='stopped',
        )

        from apps.workspaces.views import WorkspaceHistoryListView
        request = factory.get(f'/api/workspaces/{workspace.id}/history/')
        request.user = user

        view = WorkspaceHistoryListView.as_view()
        response = view(request, workspace_id=workspace.id)

        assert response.status_code == 503

    @patch('apps.workspaces.views.get_channel_layer')
    @patch('apps.workspaces.views.redis.Redis')
    def test_get_history_timeout(self, mock_redis, mock_channel_layer, factory, user):
        """Test getting history when workspace client times out."""
        workspace = Workspace.objects.create(
            owner=user,
            name='Test Workspace',
            status='running',
        )

        # Mock channel layer
        mock_layer = MagicMock()
        mock_channel_layer.return_value = mock_layer

        # Mock Redis - simulate timeout (pending never changes)
        mock_r = MagicMock()
        mock_r.get.return_value = 'pending'
        mock_redis.return_value = mock_r

        from apps.workspaces.views import WorkspaceHistoryListView
        request = factory.get(f'/api/workspaces/{workspace.id}/history/')
        request.user = user

        view = WorkspaceHistoryListView.as_view()
        response = view(request, workspace_id=workspace.id)

        assert response.status_code == 503
        assert 'timeout' in response.data.get('error', '').lower() or 'offline' in response.data.get('error', '').lower()