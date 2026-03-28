"""
Unit tests for Workspace model and API.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth import get_user_model

from .models import Workspace
from .views import WorkspaceListView, WorkspaceDetailView
from .tasks import create_workspace_container, delete_workspace_container

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(
        oidc_sub='test-user-123',
        email='test@example.com',
        display_name='Test User',
    )


@pytest.fixture
def other_user():
    """Create another test user."""
    return User.objects.create_user(
        oidc_sub='other-user-456',
        email='other@example.com',
        display_name='Other User',
    )


@pytest.fixture
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
        assert workspace.preview_url == f'http://{workspace.id}.preview.local'

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