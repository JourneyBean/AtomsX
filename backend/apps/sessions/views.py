"""
Session API Views.

Provides REST API endpoints for Agent conversation:
- POST /api/sessions/ - Start a new session
- GET /api/sessions/:id/ - Get session with message history
- GET /api/sessions/:id/stream/ - SSE streaming endpoint
- POST /api/sessions/:id/messages/ - Send a message
- POST /api/sessions/:id/interrupt/ - Interrupt current response
- POST /api/sessions/:id/resume/ - Resume session with claude_session_id
"""
import json
import logging
import redis
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from apps.workspaces.models import Workspace
from apps.workspaces.consumers import (
    send_task_to_workspace,
    send_resume_to_workspace,
    send_interrupt_to_workspace,
)
from .models import Session
from .serializers import SessionSerializer, SendMessageSerializer, ResumeSessionSerializer
from .tasks import process_agent_message, interrupt_agent_task, get_redis_client
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class SessionStartView(APIView):
    """
    Start a new Agent conversation session.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Start a new session for a workspace.

        workspace_id is passed as a query parameter: ?workspace_id=...
        """
        # Get workspace_id from query params
        workspace_id = request.GET.get('workspace_id')
        if not workspace_id:
            return Response(
                {'error': 'workspace_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get workspace and verify ownership
        workspace = get_object_or_404(Workspace, id=workspace_id)

        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check workspace is running
        if workspace.status != 'running':
            return Response(
                {'error': f'Workspace is not running (status: {workspace.status})'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create session
        session = Session.objects.create(
            workspace=workspace,
            user=request.user,
            messages=[],
            status='active',
        )

        logger.info(f'Created session {session.id} for workspace {workspace_id}')

        return Response(
            SessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name='dispatch')
class SessionDetailView(APIView):
    """
    Get session details with message history.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """
        Get session with full message history.
        """
        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(SessionSerializer(session).data)


@method_decorator(csrf_exempt, name='dispatch')
class SessionStreamView(View):
    """
    SSE streaming endpoint for Agent responses.

    Uses Django View instead of DRF APIView to avoid content negotiation
    issues with SSE (406 Not Acceptable).
    """

    def get(self, request, session_id):
        """
        Stream Agent responses via SSE.

        Connect to this endpoint to receive streaming responses.
        The client should keep the connection open to receive events.
        """
        logger.info(f'SSE stream request: session_id={session_id}, user={request.user}, authenticated={request.user.is_authenticated}')

        # Check authentication
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            logger.warning(f'SSE stream unauthorized: session_id={session_id}')
            return JsonResponse({'error': 'Authentication required'}, status=401)

        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            from django.http import JsonResponse
            return JsonResponse({'error': 'Access denied'}, status=403)

        # Check if there's a message to process
        message_content = request.GET.get('message')

        if message_content:
            # Add user message to session
            user_message = session.add_message('user', message_content, 'complete')

            # Create placeholder for agent response
            agent_message = session.add_message('agent', '', 'streaming')

            # Audit user message
            create_audit_log(
                event_type='MESSAGE_SENT',
                user_id=request.user.id,
                session_id=session.id,
                workspace_id=session.workspace_id,
                message_role='user',
                message_summary=message_content[:200],
            )

            # Trigger async processing
            process_agent_message.delay(
                str(session.id),
                agent_message['id'],
                message_content,
            )

        # Return SSE stream
        return StreamingHttpResponse(
            self._event_stream(session_id),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )

    def _event_stream(self, session_id: str):
        """
        Generate SSE events from Redis pub/sub.
        """
        # Convert UUID to string if needed
        session_id_str = str(session_id)

        r = get_redis_client()
        pubsub = r.pubsub()
        channel = f'session:{session_id_str}'

        try:
            pubsub.subscribe(channel)

            # Send initial connection event (unnamed, so onmessage receives it)
            yield f'data: {json.dumps({"type": "connected", "session_id": session_id_str})}\n\n'

            # Listen for events
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    event = json.loads(data)

                    # Send as unnamed event (onmessage will receive it)
                    yield f'data: {json.dumps(event)}\n\n'

                    # Stop streaming if done or error
                    event_type = event.get('type')
                    if event_type in ('done', 'error', 'interrupted'):
                        break

        except GeneratorExit:
            # Client disconnected
            logger.info(f'SSE client disconnected for session {session_id_str}')

        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
            r.close()


@method_decorator(csrf_exempt, name='dispatch')
class SessionMessageView(APIView):
    """
    Send a message to the Agent.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """
        Send a message to the Agent and start streaming.

        Uses WebSocket to communicate with Workspace Client if connected,
        otherwise falls back to Celery task (deprecated).
        """
        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check session is active
        if session.status != 'active':
            return Response(
                {'error': f'Session is not active (status: {session.status})'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_content = serializer.validated_data['content']

        # Add user message
        user_message = session.add_message('user', message_content, 'complete')

        # Create placeholder for agent response
        agent_message = session.add_message('agent', '', 'streaming')

        # Audit user message
        create_audit_log(
            event_type='MESSAGE_SENT',
            user_id=request.user.id,
            session_id=session.id,
            workspace_id=session.workspace_id,
            message_role='user',
            message_summary=message_content[:200],
        )

        # Check if workspace client is connected via WebSocket
        channel_layer = get_channel_layer()
        workspace_id = str(session.workspace_id)

        # Check for WebSocket connection by looking for active group members
        # This is a heuristic - we assume if there's a group, client is connected
        try:
            # Send task via WebSocket to Workspace Client
            async_to_sync(send_task_to_workspace)(
                channel_layer,
                workspace_id,
                str(session.id),
                message_content,
            )

            logger.info(f'Sent task to workspace client for session {session_id}')

            return Response({
                'message_id': agent_message['id'],
                'stream_url': f'/api/sessions/{session_id}/stream/',
                'transport': 'websocket',
            })

        except Exception as e:
            # Fallback to Celery task if WebSocket fails
            logger.warning(f'WebSocket send failed, falling back to Celery: {e}')

            task = process_agent_message.delay(
                str(session.id),
                agent_message['id'],
                message_content,
            )

            return Response({
                'message_id': agent_message['id'],
                'task_id': task.id,
                'stream_url': f'/api/sessions/{session_id}/stream/',
                'transport': 'celery',
            })


@method_decorator(csrf_exempt, name='dispatch')
class SessionInterruptView(APIView):
    """
    Interrupt an ongoing Agent response.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """
        Request an interrupt for the current Agent task.

        Uses WebSocket to communicate with Workspace Client if connected,
        otherwise falls back to Celery task.
        """
        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Send interrupt via WebSocket
        channel_layer = get_channel_layer()
        workspace_id = str(session.workspace_id)

        try:
            async_to_sync(send_interrupt_to_workspace)(
                channel_layer,
                workspace_id,
                str(session_id),
            )

            logger.info(f'Sent interrupt to workspace client for session {session_id}')

            return Response({
                'status': 'interrupt_requested',
                'transport': 'websocket',
            })

        except Exception as e:
            # Fallback to Celery
            logger.warning(f'WebSocket interrupt failed, falling back to Celery: {e}')

            task_id = request.data.get('task_id')
            if task_id:
                interrupt_agent_task.delay(task_id, str(session_id), '')
                return Response({
                    'status': 'interrupt_requested',
                    'task_id': task_id,
                    'transport': 'celery',
                })

            return Response({
                'error': 'WebSocket unavailable and no task_id provided',
                'status': status.HTTP_400_BAD_REQUEST,
            })


@method_decorator(csrf_exempt, name='dispatch')
class SessionResumeView(APIView):
    """
    Resume a session from history directory.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        """
        Resume an existing Claude session from history.

        Reads history_session_id from request, then Workspace Client
        loads the session from /home/user/history/{history_session_id}/.

        The history directory structure is managed by Workspace Client,
        not by Backend. Backend just passes the session ID to resume.
        """
        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ResumeSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        history_session_id = serializer.validated_data['history_session_id']
        message_content = serializer.validated_data.get('content', '')

        # Add user message if provided
        if message_content:
            user_message = session.add_message('user', message_content, 'complete')
            agent_message = session.add_message('agent', '', 'streaming')

            # Audit
            create_audit_log(
                event_type='MESSAGE_SENT',
                user_id=request.user.id,
                session_id=session.id,
                workspace_id=session.workspace_id,
                message_role='user',
                message_summary=message_content[:200],
            )

        # Send resume via WebSocket
        channel_layer = get_channel_layer()
        workspace_id = str(session.workspace_id)

        try:
            async_to_sync(send_resume_to_workspace)(
                channel_layer,
                workspace_id,
                str(session_id),
                history_session_id,  # This is the history session folder name
                message_content,
            )

            logger.info(f'Sent resume to workspace client for session {session_id}')

            return Response({
                'status': 'resume_requested',
                'history_session_id': history_session_id,
                'transport': 'websocket',
            })

        except Exception as e:
            logger.error(f'WebSocket resume failed: {e}')

            return Response(
                {'error': 'WebSocket communication failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )