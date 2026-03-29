"""
Workspace API Views.

Provides REST API endpoints for workspace management:
- POST /api/workspaces/ - Create a new workspace
- GET /api/workspaces/ - List user's workspaces
- GET /api/workspaces/:id/ - Get workspace details
- DELETE /api/workspaces/:id/ - Delete a workspace
- GET /api/workspaces/:id/tree/ - Get directory tree (file browser)
- GET /api/workspaces/:id/files/<path> - Get file content (file browser)
- GET /api/internal/agent-config/:workspace_id/ - Get agent config (internal)
"""
import logging
import os
import mimetypes
from pathlib import Path
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseForbidden
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import Workspace
from .serializers import WorkspaceSerializer, CreateWorkspaceSerializer
from .tasks import create_workspace_container, delete_workspace_container
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)

# Internal API token for service-to-service communication
INTERNAL_API_TOKEN = os.environ.get('ATOMSX_INTERNAL_API_TOKEN', 'dev-internal-token')


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceListView(APIView):
    """
    API view for listing and creating workspaces.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        List all workspaces owned by the current user.
        """
        workspaces = Workspace.objects.filter(owner=request.user)
        serializer = WorkspaceSerializer(workspaces, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Create a new workspace.
        """
        serializer = CreateWorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']

        # Check for duplicate name
        if Workspace.objects.filter(owner=request.user, name=name).exists():
            return Response(
                {'error': 'Workspace name already exists'},
                status=status.HTTP_409_CONFLICT,
            )

        # Create workspace record
        workspace = Workspace.objects.create(
            owner=request.user,
            name=name,
            status='creating',
        )

        # Trigger async container creation
        create_workspace_container.delay(str(workspace.id))

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_STATUS_CHANGE',
            user_id=request.user.id,
            workspace_id=workspace.id,
            previous_status=None,
            new_status='creating',
        )

        logger.info(f'Created workspace {workspace.id} for user {request.user.id}')

        return Response(
            WorkspaceSerializer(workspace).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceDetailView(APIView):
    """
    API view for getting, updating, and deleting a single workspace.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        """
        Get details of a specific workspace.
        """
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = WorkspaceSerializer(workspace)
        return Response(serializer.data)

    def delete(self, request, workspace_id):
        """
        Delete a workspace.

        If workspace is already in 'deleting' status:
        - Check if deletion task is stuck (exceeded timeout threshold)
        - If stuck, re-trigger deletion task
        - If still in progress, return 202 (deletion already in progress)
        """
        from django.conf import settings
        from django.utils import timezone
        import datetime

        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Handle workspace already in deleting status
        if workspace.status == 'deleting':
            # Check if deletion task is stuck
            # Use WORKSPACE_DELETION_TIMEOUT or default to 5 minutes
            deletion_timeout = getattr(settings, 'WORKSPACE_DELETION_TIMEOUT', 300)
            time_since_update = timezone.now() - workspace.updated_at

            if time_since_update.total_seconds() > deletion_timeout:
                # Deletion task appears stuck, re-trigger
                logger.warning(
                    f'Workspace {workspace_id} deletion appears stuck '
                    f'(updated_at: {workspace.updated_at}, elapsed: {time_since_update.total_seconds()}s), '
                    f're-triggering deletion task'
                )
                # Trigger async container deletion again
                delete_workspace_container.delay(str(workspace.id))
                return Response(
                    {'message': 'Deletion task re-triggered (previous task appeared stuck)'},
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                # Deletion is in progress
                return Response(
                    {'message': 'Workspace deletion is already in progress'},
                    status=status.HTTP_202_ACCEPTED,
                )

        # Update status to deleting
        previous_status = workspace.status
        workspace.transition_status('deleting')
        workspace.save()

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_STATUS_CHANGE',
            user_id=request.user.id,
            workspace_id=workspace.id,
            previous_status=previous_status,
            new_status='deleting',
        )

        # Trigger async container deletion
        delete_workspace_container.delay(str(workspace.id))

        logger.info(f'Deleting workspace {workspace_id}')

        return Response(status=status.HTTP_202_ACCEPTED)


@method_decorator(csrf_exempt, name='dispatch')
class InternalAgentConfigView(APIView):
    """
    Internal API endpoint for Workspace Client to fetch agent configuration.

    This endpoint is called by Workspace Client containers to get
    the Anthropic API key and base URL. It uses a simple token-based
    authentication for service-to-service communication.

    Security:
    - Requires ATOMSX_INTERNAL_API_TOKEN header
    - Token should be set in environment and kept secret
    - This is NOT a user-facing API
    """

    permission_classes = [AllowAny]  # Auth handled via internal token

    def get(self, request, workspace_id):
        """
        Get agent configuration for a workspace.

        Returns:
            - anthropic_api_key: API key for Anthropic API
            - anthropic_base_url: Base URL for Anthropic API (optional)
        """
        # Validate internal API token
        auth_header = request.headers.get('X-Internal-Token', '')
        if auth_header != INTERNAL_API_TOKEN:
            logger.warning(f'Invalid internal API token for agent config request')
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Verify workspace exists
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Return agent configuration
        config = {
            'anthropic_api_key': settings.ANTHROPIC_API_KEY,
        }

        # Add base URL if configured
        anthropic_base_url = os.environ.get('ANTHROPIC_BASE_URL', '')
        if anthropic_base_url:
            config['anthropic_base_url'] = anthropic_base_url

        # Add model if configured
        anthropic_model = os.environ.get('ANTHROPIC_MODEL', '')
        if anthropic_model:
            config['anthropic_model'] = anthropic_model

        logger.info(f'Agent config requested for workspace {workspace_id}')

        return Response(config)


# ============================================================================
# File Browser Constants and Utilities
# ============================================================================

# File size limit for text content display (2MB)
FILE_SIZE_LIMIT = 2 * 1024 * 1024

# Image extensions for direct display
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'}

# Extension to Monaco Editor language mapping
EXT_TO_LANGUAGE = {
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.vue': 'vue',
    '.py': 'python',
    '.json': 'json',
    '.html': 'html',
    '.htm': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.sass': 'scss',
    '.less': 'less',
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.sh': 'shell',
    '.bash': 'shell',
    '.zsh': 'shell',
    '.sql': 'sql',
    '.xml': 'xml',
    '.toml': 'toml',
    '.ini': 'ini',
    '.env': 'plaintext',
    '.txt': 'plaintext',
    '.log': 'plaintext',
    '.cfg': 'plaintext',
    '.conf': 'plaintext',
    '.dockerfile': 'dockerfile',
    '.makefile': 'makefile',
    '.r': 'r',
    '.rs': 'rust',
    '.go': 'go',
    '.java': 'java',
    '.kt': 'kotlin',
    '.kts': 'kotlin',
    '.swift': 'swift',
    '.c': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.rb': 'ruby',
    '.php': 'php',
    '.lua': 'lua',
    '.pl': 'perl',
    '.pm': 'perl',
    '.ex': 'elixir',
    '.exs': 'elixir',
    '.erl': 'erlang',
    '.hrl': 'erlang',
    '.scala': 'scala',
    '.clj': 'clojure',
    '.cljs': 'clojure',
    '.vim': 'vim',
    '.lua': 'lua',
    '.graphql': 'graphql',
    '.gql': 'graphql',
}


def validate_file_path(relative_path: str) -> bool:
    """
    Validate that a relative path is safe (no directory traversal).

    Returns True if path is safe, False otherwise.
    """
    if not relative_path:
        return True  # Empty path is valid (root)

    # Check for absolute path
    if relative_path.startswith('/'):
        return False

    # Check for directory traversal
    if '..' in relative_path.split('/'):
        return False

    # Check for null bytes
    if '\x00' in relative_path:
        return False

    return True


def get_workspace_file_base_path(workspace: Workspace) -> Path:
    """
    Get the base path for workspace files.

    Returns the path to the workspace directory within user data.
    """
    if not workspace.data_dir_path:
        return None
    return Path(workspace.data_dir_path) / 'workspace'


def get_file_type(file_path: Path, file_size: int) -> str:
    """
    Determine file type based on extension and content.

    Returns: 'image', 'text', 'binary', or 'too_large'
    """
    ext = file_path.suffix.lower()

    # Check for image
    if ext in IMAGE_EXTENSIONS:
        return 'image'

    # Check for size limit
    if file_size > FILE_SIZE_LIMIT:
        return 'too_large'

    # Try to detect if text by reading a sample
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(8192)  # Read first 8KB
            # Try UTF-8 decode
            sample.decode('utf-8')
            return 'text'
    except (UnicodeDecodeError, IOError):
        return 'binary'


def get_language_from_extension(file_path: Path) -> str:
    """
    Get Monaco Editor language from file extension.
    """
    ext = file_path.suffix.lower()

    # Special handling for files without extension
    name_lower = file_path.name.lower()
    if name_lower == 'dockerfile':
        return 'dockerfile'
    if name_lower == 'makefile':
        return 'makefile'
    if name_lower.startswith('.env') or name_lower == '.gitignore':
        return 'plaintext'

    return EXT_TO_LANGUAGE.get(ext, 'plaintext')


def get_mime_type(file_path: Path) -> str:
    """
    Get MIME type for a file.
    """
    ext = file_path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        return mime_type

    # Default MIME types for common extensions
    MIME_DEFAULTS = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.bmp': 'image/bmp',
        '.ico': 'image/x-icon',
        '.js': 'application/javascript',
        '.ts': 'application/typescript',
        '.json': 'application/json',
        '.html': 'text/html',
        '.css': 'text/css',
        '.md': 'text/markdown',
        '.txt': 'text/plain',
        '.py': 'text/x-python',
        '.vue': 'text/x-vue',
    }
    return MIME_DEFAULTS.get(ext, 'application/octet-stream')


# ============================================================================
# File Browser Views
# ============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceFileTreeView(APIView):
    """
    API view for getting directory tree of a workspace.

    GET /api/workspaces/:id/tree/?path=<relative_path>

    Returns a list of files and directories in the specified path.
    Uses lazy loading - only returns immediate children, not nested.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        """
        Get directory tree for a workspace.
        """
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check workspace is running
        if workspace.status != 'running':
            return Response(
                {'error': f'Workspace is {workspace.status}, cannot browse files'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get relative path from query params
        relative_path = request.query_params.get('path', '').strip()

        # Validate path
        if not validate_file_path(relative_path):
            return Response(
                {'error': 'Invalid path'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get base path
        base_path = get_workspace_file_base_path(workspace)
        if not base_path:
            return Response(
                {'error': 'Workspace data directory not configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build full path
        if relative_path:
            full_path = base_path / relative_path
        else:
            full_path = base_path

        # Check path exists and is within workspace
        try:
            full_path = full_path.resolve()
            base_path = base_path.resolve()

            # Security: ensure resolved path is within base path
            if not str(full_path).startswith(str(base_path)):
                return Response(
                    {'error': 'Path outside workspace'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not full_path.exists():
                return Response(
                    {'error': 'Path not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not full_path.is_dir():
                return Response(
                    {'error': 'Path is not a directory'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logger.error(f'Error resolving path: {e}')
            return Response(
                {'error': 'Error accessing path'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # List directory contents
        nodes = []
        try:
            for item in sorted(full_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden files (starting with .) except .env, .gitignore etc
                if item.name.startswith('.') and item.name not in ['.env', '.env.local', '.env.development', '.env.production', '.gitignore', '.dockerignore']:
                    continue

                item_path = str(item.relative_to(base_path))
                is_dir = item.is_dir()

                node = {
                    'name': item.name,
                    'type': 'directory' if is_dir else 'file',
                    'path': item_path,
                }

                if is_dir:
                    # Check if directory has children (for expand arrow)
                    try:
                        has_children = any(
                            not child.name.startswith('.') or child.name in ['.env', '.gitignore']
                            for child in item.iterdir()
                        )
                        node['has_children'] = has_children
                    except PermissionError:
                        node['has_children'] = False
                else:
                    # File info
                    try:
                        file_size = item.stat().st_size
                        node['size'] = file_size
                        node['language'] = get_language_from_extension(item)
                    except OSError:
                        node['size'] = 0
                        node['language'] = 'plaintext'

                nodes.append(node)

        except PermissionError as e:
            logger.error(f'Permission error listing directory: {e}')
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response({'nodes': nodes})


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceFileContentView(APIView):
    """
    API view for getting file content or raw binary stream.

    GET /api/workspaces/:id/files/<path>
    Returns file content info (text/binary/image/too_large)

    GET /api/workspaces/:id/files/<path>?raw=1
    Returns raw binary stream for images and downloads
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, file_path):
        """
        Get file content or raw stream.
        """
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check workspace is running
        if workspace.status != 'running':
            return Response(
                {'error': f'Workspace is {workspace.status}, cannot read files'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate path
        if not validate_file_path(file_path):
            return Response(
                {'error': 'Invalid path'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get base path
        base_path = get_workspace_file_base_path(workspace)
        if not base_path:
            return Response(
                {'error': 'Workspace data directory not configured'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build full path
        full_path = base_path / file_path

        # Resolve and check path is within workspace
        try:
            full_path = full_path.resolve()
            base_path = base_path.resolve()

            if not str(full_path).startswith(str(base_path)):
                return Response(
                    {'error': 'Path outside workspace'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not full_path.exists():
                return Response(
                    {'error': 'File not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not full_path.is_file():
                return Response(
                    {'error': 'Path is not a file'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logger.error(f'Error resolving file path: {e}')
            return Response(
                {'error': 'Error accessing file'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get file size
        try:
            file_size = full_path.stat().st_size
        except OSError:
            file_size = 0

        # Check if raw mode requested
        raw_mode = request.query_params.get('raw', '0') == '1'

        if raw_mode:
            # Return raw binary stream
            mime_type = get_mime_type(full_path)
            try:
                with open(full_path, 'rb') as f:
                    content = f.read()
                response = HttpResponse(content, content_type=mime_type)
                # Set filename for download
                response['Content-Disposition'] = f'inline; filename="{full_path.name}"'
                return response
            except IOError as e:
                logger.error(f'Error reading file: {e}')
                return Response(
                    {'error': 'Error reading file'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Determine file type
        file_type = get_file_type(full_path, file_size)

        # Build response based on type
        if file_type == 'image':
            return Response({
                'type': 'image',
                'mime_type': get_mime_type(full_path),
                'size': file_size,
            })

        elif file_type == 'too_large':
            return Response({
                'type': 'too_large',
                'size': file_size,
                'message': '文件过大，无法展示',
            })

        elif file_type == 'binary':
            return Response({
                'type': 'binary',
                'size': file_size,
                'message': '无法打开此文件类型',
            })

        else:  # text
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return Response({
                    'type': 'text',
                    'content': content,
                    'language': get_language_from_extension(full_path),
                    'size': file_size,
                })
            except UnicodeDecodeError:
                # Shouldn't happen since we checked, but handle gracefully
                return Response({
                    'type': 'binary',
                    'size': file_size,
                    'message': '无法打开此文件类型',
                })
            except IOError as e:
                logger.error(f'Error reading file: {e}')
                return Response(
                    {'error': 'Error reading file'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceHistoryListView(APIView):
    """
    API view for getting Claude session history from Workspace Client.

    GET /api/workspaces/:id/history/

    Returns list of history sessions sorted by last_activity descending.
    Each session includes: history_session_id, first_message, last_activity.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        """
        Get Claude session history for a workspace.

        Sends a WebSocket message to Workspace Client and waits for response.
        Returns 503 if Workspace Client is not connected or times out.
        """
        import uuid
        import json
        import time
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        import redis

        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check workspace is running
        if workspace.status != 'running':
            return Response(
                {'error': f'Workspace is {workspace.status}, cannot get history'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Get channel layer
        channel_layer = get_channel_layer()
        if not channel_layer:
            return Response(
                {'error': 'WebSocket layer not available'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Get Redis client for response storage
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=2,
            decode_responses=True,
        )

        try:
            # Set pending request in Redis
            r.set(f'history_request:{request_id}', 'pending', ex=10)

            # Send get_history request via WebSocket
            async_to_sync(channel_layer.group_send)(
                f'workspace_{workspace_id}',
                {
                    'type': 'history.message',
                    'request_id': request_id,
                }
            )

            # Poll for response (wait up to 5 seconds)
            max_wait = 5.0
            poll_interval = 0.1
            elapsed = 0.0

            while elapsed < max_wait:
                response_data = r.get(f'history_request:{request_id}')

                if response_data and response_data != 'pending':
                    # Got response
                    sessions = json.loads(response_data)
                    return Response({'sessions': sessions})

                time.sleep(poll_interval)
                elapsed += poll_interval

            # Timeout - Workspace Client not responding
            logger.warning(f'History request timeout for workspace {workspace_id}')
            return Response(
                {'error': 'workspace client timeout'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception as e:
            logger.error(f'Error getting history: {e}')
            return Response(
                {'error': 'Failed to get history'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        finally:
            # Cleanup Redis
            r.delete(f'history_request:{request_id}')
            r.close()


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceHistoryMessagesView(APIView):
    """
    API view for getting messages from a specific Claude session history.

    GET /api/workspaces/:id/history/:history_session_id/

    Returns list of messages from the history session.
    Each message includes: role, content, timestamp, status.

    This endpoint does NOT call Claude Agent SDK - it just retrieves
    stored messages from the history folder.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, history_session_id):
        """
        Get messages from a specific history session.

        Sends a WebSocket message to Workspace Client and waits for response.
        Returns 503 if Workspace Client is not connected or times out.
        """
        import uuid
        import json
        import time
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        import redis

        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check workspace is running
        if workspace.status != 'running':
            return Response(
                {'error': f'Workspace is {workspace.status}, cannot get history'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Get channel layer
        channel_layer = get_channel_layer()
        if not channel_layer:
            return Response(
                {'error': 'WebSocket layer not available'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Get Redis client for response storage
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT),
            db=2,
            decode_responses=True,
        )

        try:
            # Set pending request in Redis
            r.set(f'history_messages_request:{request_id}', 'pending', ex=10)

            # Send get_history_messages request via WebSocket
            async_to_sync(channel_layer.group_send)(
                f'workspace_{workspace_id}',
                {
                    'type': 'history_messages.message',
                    'request_id': request_id,
                    'history_session_id': history_session_id,
                }
            )

            # Poll for response (wait up to 5 seconds)
            max_wait = 5.0
            poll_interval = 0.1
            elapsed = 0.0

            while elapsed < max_wait:
                response_data = r.get(f'history_messages_request:{request_id}')

                if response_data and response_data != 'pending':
                    # Got response
                    data = json.loads(response_data)
                    return Response({
                        'messages': data.get('messages', []),
                        'history_session_id': data.get('history_session_id'),
                    })

                time.sleep(poll_interval)
                elapsed += poll_interval

            # Timeout - Workspace Client not responding
            logger.warning(f'History messages request timeout for workspace {workspace_id}')
            return Response(
                {'error': 'workspace client timeout'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception as e:
            logger.error(f'Error getting history messages: {e}')
            return Response(
                {'error': 'Failed to get history messages'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        finally:
            # Cleanup Redis
            r.delete(f'history_messages_request:{request_id}')
            r.close()