"""
Custom authentication classes for Django REST Framework.
"""
from rest_framework import authentication
from django.contrib.auth import get_user_model


class CsrfExemptSessionAuthentication(authentication.SessionAuthentication):
    """
    Session authentication that doesn't require CSRF token.

    This is appropriate for SPA frontends where:
    - CORS is properly configured to restrict origins
    - SameSite cookie policy prevents cross-site requests
    - The frontend and backend are on the same domain through a gateway

    CSRF protection is redundant when these protections are in place,
    as cross-site attacks are blocked by browser security policies.
    """

    def enforce_csrf(self, request):
        # Skip CSRF enforcement - rely on CORS and SameSite instead
        return