"""
Unit tests for Session API and Agent conversation.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth import get_user_model

from .models import Session
from .views import SessionStartView, SessionDetailView, SessionStreamView

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(
        oidc_sub='test-user-session',
        email='session@example.com',
        display_name='Session User',
    )


@pytest.fixture
def other_user():
    """Create another test user."""
    return User.objects.create_user(
        oidc_sub='other-user-session',
        email='other-session@example.com',
        display_name='Other User',
    )


@pytest.fixture
def workspace(user):
    """Create a test workspace."""
    from apps.workspaces.models import Workspace
    return Workspace.objects.create(
        owner=user,
        name='Test Workspace',
        status='running',
        container_id='container-session-test',
    )


@pytest.fixture
def session(workspace, user):
    """Create a test session."""
    return Session.objects.create(
        workspace=workspace,
        user=user,
        messages=[
            {'id': 'msg-1', 'role': 'user', 'content': 'Hello', 'status': 'complete'},
            {'id': 'msg-2', 'role': 'agent', 'content': 'Hi there!', 'status': 'complete'},
        ],
        status='active',
    )


@pytest.fixture
def factory():
    return RequestFactory()


class TestSessionModel:
    """Tests for the Session model."""

    def test_create_session(self, workspace, user):
        """Test creating a session."""
        session = Session.objects.create(
            workspace=workspace,
            user=user,
        )

        assert session.workspace == workspace
        assert session.user == user
        assert session.status == 'active'
        assert session.messages == []

    def test_add_message(self, session):
        """Test adding a message to session."""
        msg = session.add_message('user', 'Test message')

        assert msg['role'] == 'user'
        assert msg['content'] == 'Test message'
        assert msg['status'] == 'complete'
        assert len(session.messages) == 3

    def test_update_message_status(self, session):
        """Test updating message status."""
        session.update_message_status('msg-1', 'interrupted')

        assert session.messages[0]['status'] == 'interrupted'


class TestSessionAPI:
    """Tests for Session API views."""

    def test_start_session(self, factory, user, workspace):
        """Test starting a new session."""
        request = factory.post(f'/api/sessions/?workspace_id={workspace.id}')
        request.user = user

        view = SessionStartView.as_view()
        response = view(request, workspace_id=workspace.id)

        assert response.status_code == 201
        assert 'id' in response.data

    def test_start_session_forbidden(self, factory, other_user, workspace):
        """Test starting session on another user's workspace."""
        request = factory.post(f'/api/sessions/?workspace_id={workspace.id}')
        request.user = other_user

        view = SessionStartView.as_view()
        response = view(request, workspace_id=workspace.id)

        assert response.status_code == 403

    def test_get_session(self, factory, user, session):
        """Test getting session details."""
        request = factory.get(f'/api/sessions/{session.id}/')
        request.user = user

        view = SessionDetailView.as_view()
        response = view(request, session_id=session.id)

        assert response.status_code == 200
        assert len(response.data['messages']) == 2

    def test_get_session_forbidden(self, factory, other_user, session):
        """Test getting another user's session."""
        request = factory.get(f'/api/sessions/{session.id}/')
        request.user = other_user

        view = SessionDetailView.as_view()
        response = view(request, session_id=session.id)

        assert response.status_code == 403


class TestAgentTasks:
    """Tests for Agent processing tasks."""

    @patch('apps.sessions.tasks.get_redis_client')
    @patch('apps.sessions.tasks.Anthropic')
    def test_process_agent_message(self, mock_anthropic, mock_redis, session):
        """Test Agent message processing."""
        from apps.sessions.tasks import process_agent_message

        # Mock Redis
        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        # Mock Anthropic client
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.text_stream = ['Hello', ' world']
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic.return_value = mock_client

        # Add agent message placeholder
        agent_msg = session.add_message('agent', '', 'streaming')

        # Run task
        process_agent_message(str(session.id), agent_msg['id'], 'Test message')

        # Verify message updated
        session.refresh_from_db()
        assert session.messages[-1]['status'] == 'complete'