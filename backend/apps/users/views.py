"""
OIDC Authentication Views for AtomsX.

Handles login, logout, callback, and session verification.
"""
import secrets
import logging
from django.shortcuts import redirect
from django.contrib.auth import login, logout
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings

from .models import User
from .oidc_client import oidc_client
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


class OIDCLoginView(View):
    """
    Initiate OIDC login flow.
    Redirects user to the OIDC provider's authorization endpoint.
    """

    def get(self, request):
        # Generate a random state for CSRF protection
        state = secrets.token_urlsafe(32)
        request.session['oidc_state'] = state

        # Generate authorization URL
        auth_url = oidc_client.get_authorization_url(state)

        # Audit the login initiation
        create_audit_log(
            event_type='LOGIN',
            ip_address=request.META.get('REMOTE_ADDR'),
            metadata={'action': 'login_initiated'},
        )

        return redirect(auth_url)


@method_decorator(csrf_exempt, name='dispatch')
class OIDCCallbackView(View):
    """
    Handle OIDC callback after user authenticates with provider.
    Exchanges code for tokens, retrieves user info, creates/updates user.
    """

    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')

        # Verify state matches
        stored_state = request.session.get('oidc_state')
        if not state or state != stored_state:
            logger.warning('OIDC callback with invalid state')
            return JsonResponse({'error': 'Invalid state'}, status=400)

        # Clear the stored state
        request.session.pop('oidc_state', None)

        if not code:
            error = request.GET.get('error', 'unknown')
            logger.warning(f'OIDC callback with error: {error}')
            create_audit_log(
                event_type='LOGIN',
                ip_address=request.META.get('REMOTE_ADDR'),
                error_message=f'OIDC provider returned error: {error}',
            )
            return redirect('/login?error=auth_failed')

        try:
            # Exchange code for tokens
            token_response = oidc_client.exchange_code_for_token(code)
            access_token = token_response.get('access_token')

            # Get user info
            user_info = oidc_client.get_user_info(access_token)
            oidc_sub = user_info.get('sub')
            email = user_info.get('email')
            display_name = user_info.get('name') or user_info.get('preferred_username') or email
            avatar_url = user_info.get('picture')

            if not oidc_sub or not email:
                logger.error('OIDC user info missing sub or email')
                return redirect('/login?error=missing_info')

            # Get or create user
            user, created = User.objects.get_or_create_from_oidc(
                oidc_sub=oidc_sub,
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
            )

            # Log user in
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Audit successful login
            create_audit_log(
                event_type='LOGIN',
                user_id=user.id,
                oidc_sub=oidc_sub,
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            logger.info(f'User logged in: {user.email} (created: {created})')

            # Redirect to frontend
            return redirect('/auth/callback')

        except Exception as e:
            logger.exception(f'OIDC callback error: {e}')
            create_audit_log(
                event_type='LOGIN',
                ip_address=request.META.get('REMOTE_ADDR'),
                error_message=str(e),
            )
            return redirect('/login?error=auth_failed')


@method_decorator(csrf_exempt, name='dispatch')
class OIDCLogoutView(View):
    """
    Log out user and optionally redirect to OIDC provider logout.
    """

    def post(self, request):
        user_id = request.user.id if request.user.is_authenticated else None
        oidc_sub = request.user.oidc_sub if request.user.is_authenticated else None

        # Logout from Django session
        logout(request)

        # Audit logout
        create_audit_log(
            event_type='LOGOUT',
            user_id=user_id,
            oidc_sub=oidc_sub,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        # Optionally redirect to OIDC provider logout
        provider_logout_url = oidc_client.get_logout_url(
            post_logout_redirect_uri=settings.OIDC_REDIRECT_URI.replace('/callback', '/login')
        )

        if provider_logout_url:
            return JsonResponse({'redirect': provider_logout_url})
        else:
            return JsonResponse({'redirect': '/login'})


class CurrentUserView(View):
    """
    Return current user information for authenticated sessions.
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)

        user = request.user
        return JsonResponse({
            'id': str(user.id),
            'email': user.email,
            'display_name': user.display_name,
            'avatar_url': user.avatar_url,
            'oidc_sub': user.oidc_sub,
            'created_at': user.created_at.isoformat(),
        })


class AuthVerifyView(View):
    """
    Verify authentication and workspace ownership for Preview access.
    Called by OpenResty gateway before proxying to workspace containers.
    """

    def get(self, request):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse(
                {'error': 'unauthorized', 'message': 'Authentication required'},
                status=401,
            )

        workspace_id = request.headers.get('X-Workspace-Id') or request.GET.get('workspace_id')
        if workspace_id:
            # Check workspace ownership
            from apps.workspaces.models import Workspace

            try:
                workspace = Workspace.objects.get(id=workspace_id)
                if workspace.owner != request.user:
                    create_audit_log(
                        event_type='PREVIEW_ACCESS_DENIED',
                        user_id=request.user.id,
                        workspace_id=workspace_id,
                        ip_address=request.META.get('REMOTE_ADDR'),
                        reason='not_owner',
                    )
                    return JsonResponse(
                        {'error': 'forbidden', 'message': 'Access denied to this workspace'},
                        status=403,
                    )

                # Return user info and container host
                create_audit_log(
                    event_type='PREVIEW_ACCESS',
                    user_id=request.user.id,
                    workspace_id=workspace_id,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                return JsonResponse({
                    'user_id': str(request.user.id),
                    'workspace_id': str(workspace_id),
                    'container_host': workspace.container_host if hasattr(workspace, 'container_host') else None,
                })

            except Workspace.DoesNotExist:
                return JsonResponse(
                    {'error': 'not_found', 'message': 'Workspace not found'},
                    status=404,
                )

        # No workspace_id provided, just verify authentication
        return JsonResponse({
            'user_id': str(request.user.id),
            'authenticated': True,
        })