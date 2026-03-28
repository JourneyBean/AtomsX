"""
OIDC Client for AtomsX.

A lightweight OIDC client implementation that supports:
- Authorization code flow
- Token exchange
- User info retrieval
- Multi-provider architecture (future extension)

This replaces mozilla-django-oidc for better control and extensibility.
"""
import requests
from typing import Optional, Dict, Any
from django.conf import settings
from urllib.parse import urlencode


class OIDCClient:
    """
    OIDC Client for authentication with external identity providers.
    """

    def __init__(
        self,
        provider_url: str = None,
        client_id: str = None,
        client_secret: str = None,
        redirect_uri: str = None,
    ):
        self.provider_url = provider_url or settings.OIDC_PROVIDER_URL
        self.client_id = client_id or settings.OIDC_CLIENT_ID
        self.client_secret = client_secret or settings.OIDC_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.OIDC_REDIRECT_URI

        # Discover OIDC endpoints (lazy loaded)
        self._discovery_document: Optional[Dict[str, Any]] = None

    def get_discovery_document(self) -> Dict[str, Any]:
        """
        Fetch the OIDC discovery document from the provider.
        """
        if self._discovery_document is None:
            discovery_url = self.provider_url.rstrip('/') + '/.well-known/openid-configuration'
            response = requests.get(discovery_url, timeout=10)
            response.raise_for_status()
            self._discovery_document = response.json()
        return self._discovery_document

    def get_authorization_url(self, state: str) -> str:
        """
        Generate the authorization URL for the OIDC provider.
        """
        discovery = self.get_discovery_document()
        auth_endpoint = discovery.get('authorization_endpoint')

        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
        }

        return f"{auth_endpoint}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange the authorization code for access token and ID token.
        """
        discovery = self.get_discovery_document()
        token_endpoint = discovery.get('token_endpoint')

        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

        response = requests.post(
            token_endpoint,
            data=data,
            timeout=10,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        response.raise_for_status()
        return response.json()

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from the OIDC provider.
        """
        discovery = self.get_discovery_document()
        userinfo_endpoint = discovery.get('userinfo_endpoint')

        response = requests.get(
            userinfo_endpoint,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_logout_url(self, post_logout_redirect_uri: str = None) -> Optional[str]:
        """
        Get the logout URL from the OIDC provider (if supported).
        """
        discovery = self.get_discovery_document()
        end_session_endpoint = discovery.get('end_session_endpoint')

        if not end_session_endpoint:
            return None

        if post_logout_redirect_uri:
            params = {'post_logout_redirect_uri': post_logout_redirect_uri}
            return f"{end_session_endpoint}?{urlencode(params)}"

        return end_session_endpoint


# Default client instance
oidc_client = OIDCClient()