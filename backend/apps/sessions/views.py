"""
Session API Views.

Provides REST API endpoints for Agent conversation:
- POST /api/sessions/ - Start a new session
- GET /api/sessions/:id/ - Get session with message history
- GET /api/sessions/:id/stream/ - SSE streaming endpoint
- POST /api/sessions/:id/messages/ - Send a message
- POST /api/sessions/:id/interrupt/ - Interrupt current response
"""
import json
import logging
import redis
from django.conf import settings
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from apps.workspaces.models import Workspace
from .models import Session
from .serializers import SessionSerializer, SendMessageSerializer
from .tasks import process_agent_message, interrupt_agent_task, get_redis_client
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class SessionStartView(APIView):
    """
    Start a new Agent conversation session.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id):
        """
        Start a new session for a workspace.
        """
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
class SessionStreamView(APIView):
    """
    SSE streaming endpoint for Agent responses.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        """
        Stream Agent responses via SSE.

        Connect to this endpoint to receive streaming responses.
        The client should keep the connection open to receive events.
        """
        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

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
                'Connection': 'keep-alive',
            },
        )

    def _event_stream(self, session_id: str):
        """
        Generate SSE events from Redis pub/sub.
        """
        r = get_redis_client()
        pubsub = r.pubsub()
        channel = f'session:{session_id}'

        try:
            pubsub.subscribe(channel)

            # Send initial connection event
            yield f'event: connected\ndata: {{"session_id": "{session_id}"}}\n\n'

            # Listen for events
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    event = json.loads(data)

                    event_type = event.pop('type', 'message')
                    yield f'event: {event_type}\ndata: {json.dumps(event)}\n\n'

                    # Stop streaming if done or error
                    if event_type in ('done', 'error', 'interrupted'):
                        break

        except GeneratorExit:
            # Client disconnected
            logger.info(f'SSE client disconnected for session {session_id}')

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

        # Trigger async processing
        task = process_agent_message.delay(
            str(session.id),
            agent_message['id'],
            message_content,
        )

        return Response({
            'message_id': agent_message['id'],
            'task_id': task.id,
            'stream_url': f'/api/sessions/{session_id}/stream/',
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
        """
        session = get_object_or_404(Session, id=session_id)

        # Check ownership
        if session.user != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task_id = request.data.get('task_id')

        if not task_id:
            return Response(
                {'error': 'task_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Request interrupt
        interrupt_agent_task.delay(task_id, str(session_id), '')

        return Response({
            'status': 'interrupt_requested',
            'task_id': task_id,
        })