"""
Unit tests for OIDC authentication.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

from .models import User
from .oidc_client import OIDCClient
from .views import OIDCLoginView, OIDCCallbackView, OIDCLogoutView


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.fixture
def mock_discovery():
    """Mock OIDC discovery document."""
    return {
        'authorization_endpoint': 'https://auth.example.com/oauth/authorize',
        'token_endpoint': 'https://auth.example.com/oauth/token',
        'userinfo_endpoint': 'https://auth.example.com/oauth/userinfo',
        'end_session_endpoint': 'https://auth.example.com/oauth/logout',
    }


@pytest.fixture
def mock_user_info():
    """Mock OIDC user info response."""
    return {
        'sub': 'user-123',
        'email': 'test@example.com',
        'name': 'Test User',
    }


@pytest.fixture
def mock_token_response():
    """Mock OIDC token response."""
    return {
        'access_token': 'test-access-token',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'id_token': 'test-id-token',
    }


class TestOIDCClient:
    """Tests for the OIDCClient class."""

    @patch('apps.users.oidc_client.requests.get')
    def test_get_discovery_document(self, mock_get, mock_discovery):
        """Test fetching the OIDC discovery document."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_discovery
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = OIDCClient(
            provider_url='https://auth.example.com/application/o/test/',
        )
        discovery = client.get_discovery_document()

        assert discovery['authorization_endpoint'] == mock_discovery['authorization_endpoint']
        mock_get.assert_called_once()

    def test_get_authorization_url(self, mock_discovery):
        """Test generating the authorization URL."""
        client = OIDCClient(
            provider_url='https://auth.example.com/application/o/test/',
            client_id='test-client',
            redirect_uri='http://localhost:8000/api/auth/callback',
        )
        client._discovery_document = mock_discovery

        auth_url = client.get_authorization_url(state='test-state')

        assert 'https://auth.example.com/oauth/authorize' in auth_url
        assert 'client_id=test-client' in auth_url
        assert 'state=test-state' in auth_url
        assert 'response_type=code' in auth_url


class TestUserModel:
    """Tests for the custom User model."""

    def test_create_user(self):
        """Test creating a user from OIDC info."""
        user = User.objects.create_user(
            oidc_sub='user-123',
            email='test@example.com',
            display_name='Test User',
        )

        assert user.oidc_sub == 'user-123'
        assert user.email == 'test@example.com'
        assert user.display_name == 'Test User'
        assert user.is_active is True
        assert user.is_staff is False

    def test_get_or_create_from_oidc_new_user(self):
        """Test creating a new user from OIDC."""
        user, created = User.objects.get_or_create_from_oidc(
            oidc_sub='new-user-456',
            email='newuser@example.com',
            display_name='New User',
        )

        assert created is True
        assert user.oidc_sub == 'new-user-456'
        assert user.email == 'newuser@example.com'

    def test_get_or_create_from_oidc_existing_user(self):
        """Test getting an existing user from OIDC."""
        # Create initial user
        User.objects.create_user(
            oidc_sub='existing-user-789',
            email='existing@example.com',
            display_name='Existing User',
        )

        # Get the same user
        user, created = User.objects.get_or_create_from_oidc(
            oidc_sub='existing-user-789',
            email='existing@example.com',
            display_name='Updated Name',
        )

        assert created is False
        assert user.display_name == 'Updated Name'


class TestOIDCViews:
    """Tests for OIDC authentication views."""

    def test_login_view_redirects(self, factory, mock_discovery):
        """Test that login view redirects to OIDC provider."""
        request = factory.get('/api/auth/login/')

        # Add session middleware
        middleware = SessionMiddleware(lambda x: x)
        middleware.process_request(request)
        request.session.save()

        with patch.object(OIDCClient, 'get_discovery_document', return_value=mock_discovery):
            view = OIDCLoginView.as_view()
            response = view(request)

        assert response.status_code == 302
        assert 'https://auth.example.com/oauth/authorize' in response.url

    def test_logout_view(self, factory):
        """Test that logout view terminates session."""
        request = factory.post('/api/auth/logout/')
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.id = 'user-id-123'
        request.user.oidc_sub = 'user-sub-123'

        # Add session middleware
        middleware = SessionMiddleware(lambda x: x)
        middleware.process_request(request)
        request.session.save()

        view = OIDCLogoutView.as_view()
        response = view(request)

        assert response.status_code == 200


class TestAuthVerifyView:
    """Tests for the auth verification endpoint."""

    def test_unauthenticated_user_returns_401(self, factory):
        """Test that unauthenticated requests return 401."""
        from apps.users.views import AuthVerifyView

        request = factory.get('/api/auth/verify/')
        request.user = MagicMock()
        request.user.is_authenticated = False

        view = AuthVerifyView.as_view()
        response = view(request)

        assert response.status_code == 401

    def test_authenticated_user_returns_user_info(self, factory):
        """Test that authenticated requests return user info."""
        from apps.users.views import AuthVerifyView

        request = factory.get('/api/auth/verify/')
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.id = 'user-id-123'

        view = AuthVerifyView.as_view()
        response = view(request)

        assert response.status_code == 200