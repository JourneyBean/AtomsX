"""
Multi-Provider OIDC Architecture

This module documents how to extend the OIDC client to support multiple providers.

Current Implementation:
- Single provider configured via environment variables
- OIDCClient class can be instantiated with custom provider settings

Future Multi-Provider Support:
1. Create an OIDCProvider model to store provider configurations:
   - name: Display name (e.g., "Google", "Okta")
   - slug: URL-friendly identifier (e.g., "google", "okta")
   - provider_url: OIDC discovery URL
   - client_id: OAuth client ID
   - client_secret: OAuth client secret
   - redirect_uri: Callback URL
   - is_active: Enable/disable provider

2. Update OIDCClient to accept a provider configuration:
   ```python
   provider = OIDCProvider.objects.get(slug='google')
   client = OIDCClient(
       provider_url=provider.provider_url,
       client_id=provider.client_id,
       client_secret=provider.client_secret,
       redirect_uri=provider.redirect_uri,
   )
   ```

3. Update User model to support multiple provider identities:
   - Add OIDCIdentity model with: user FK, provider FK, sub (unique together: provider + sub)
   - User can have multiple OIDCIdentity records linked

4. Update login flow:
   - Show provider selection page
   - Redirect to selected provider
   - Match user by OIDCIdentity

Architecture Decisions Already Made:
- OIDCClient is provider-agnostic (accepts config in constructor)
- User.oidc_sub is provider-specific but can be migrated to OIDCIdentity
- Views use the singleton oidc_client but can be updated to use per-request clients

Migration Path:
1. Create OIDCProvider and OIDCIdentity models
2. Create data migration to move existing users to OIDCIdentity
3. Update login flow to support provider selection
4. Keep backward compatibility with single-provider configuration
"""


class MultiProviderConfig:
    """
    Placeholder for multi-provider configuration.

    This class will be implemented when multi-provider support is needed.
    """

    @staticmethod
    def get_provider_configs():
        """
        Return a list of available provider configurations.

        For now, returns the single configured provider.
        """
        from django.conf import settings

        return [{
            'name': 'Default Provider',
            'slug': 'default',
            'provider_url': settings.OIDC_PROVIDER_URL,
            'client_id': settings.OIDC_CLIENT_ID,
            'client_secret': settings.OIDC_CLIENT_SECRET,
            'redirect_uri': settings.OIDC_REDIRECT_URI,
        }]