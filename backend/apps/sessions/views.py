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
from asgiref.sync import async_to_sync, sync_to_async
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
            logger.info(f'[SSE] Sending connected event for session {session_id_str}')
            yield f'data: {json.dumps({"type": "connected", "session_id": session_id_str})}\n\n'

            # Listen for events
            for message in pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    event = json.loads(data)
                    event_type = event.get('type')

                    # Log each event for debugging
                    logger.info(f'[SSE] Yielding event: type={event_type}, session={session_id_str}')

                    # Send as unnamed event (onmessage will receive it)
                    yield f'data: {json.dumps(event)}\n\n'

                    # Stop streaming if done or error
                    if event_type in ('done', 'error', 'interrupted'):
                        logger.info(f'[SSE] Stream ended for session {session_id_str}')
                        break

        except GeneratorExit:
            # Client disconnected
            logger.info(f'SSE client disconnected for session {session_id_str}')

        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
            r.close()


@method_decorator(csrf_exempt, name='dispatch')
class SessionMessageView(View):
    """
    Send a message to the Agent and receive streaming SSE response.
    """

    async def post(self, request, session_id):
        """
        Send a message and return SSE stream directly.
        """
        from django.http import JsonResponse, StreamingHttpResponse
        from asgiref.sync import sync_to_async
        import asyncio

        # Check authentication - use sync_to_async for ORM access
        @sync_to_async
        def get_user(request):
            return request.user if request.user.is_authenticated else None

        user = await get_user(request)
        if not user:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        # Get session with user prefetched to avoid sync DB access in async context
        @sync_to_async
        def get_session(session_id):
            return Session.objects.select_related('user').get(id=session_id)

        try:
            session = await get_session(session_id)
        except Session.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)

        # Check ownership
        if session.user != user:
            return JsonResponse({'error': 'Access denied'}, status=403)

        # Check session is active
        if session.status != 'active':
            return JsonResponse(
                {'error': f'Session is not active (status: {session.status})'},
                status=400,
            )

        # Parse JSON body
        try:
            body = json.loads(request.body)
            message_content = body.get('content', '')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if not message_content:
            return JsonResponse({'error': 'Content is required'}, status=400)

        # Add user message
        @sync_to_async
        def add_messages():
            session.add_message('user', message_content, 'complete')
            session.add_message('agent', '', 'streaming')

        await add_messages()

        # Audit user message (wrapped for async context)
        await sync_to_async(create_audit_log)(
            event_type='MESSAGE_SENT',
            user_id=user.id,
            session_id=session.id,
            workspace_id=session.workspace_id,
            message_role='user',
            message_summary=message_content[:200],
        )

        # Send task via WebSocket to Workspace Client
        workspace_id = str(session.workspace_id)

        try:
            await send_task_to_workspace(
                get_channel_layer(),
                workspace_id,
                str(session.id),
                message_content,
            )
            logger.info(f'Sent task to workspace client for session {session_id}')
        except Exception as e:
            logger.error(f'Failed to send task to workspace: {e}')
            return JsonResponse({'error': 'Workspace client unavailable'}, status=503)

        # Return SSE stream using async generator with thread-based Redis polling
        async def event_stream():
            session_id_str = str(session_id)
            r = get_redis_client()
            pubsub = r.pubsub()
            channel = f'session:{session_id_str}'
            loop = asyncio.get_running_loop()

            try:
                # Subscribe in thread to avoid blocking
                await loop.run_in_executor(None, pubsub.subscribe, channel)

                # Send initial connection event
                logger.info(f'[SSE] Sending connected event for session {session_id_str}')
                yield f'data: {json.dumps({"type": "connected", "session_id": session_id_str})}\n\n'

                # Poll for messages in thread to avoid blocking event loop
                while True:
                    # Get message in thread pool
                    message = await loop.run_in_executor(None, pubsub.get_message, True, 0.1)

                    if message is None:
                        # No message, yield control and continue polling
                        await asyncio.sleep(0.05)
                        continue

                    if message['type'] == 'message':
                        data = message['data']
                        event = json.loads(data)
                        event_type = event.get('type')

                        logger.info(f'[SSE] Yielding event: type={event_type}, session={session_id_str}')
                        yield f'data: {json.dumps(event)}\n\n'

                        # Yield control to event loop for proper flushing
                        await asyncio.sleep(0)

                        if event_type in ('done', 'error', 'interrupted'):
                            logger.info(f'[SSE] Stream ended for session {session_id_str}')
                            break

            except GeneratorExit:
                logger.info(f'SSE client disconnected for session {session_id_str}')
            finally:
                await loop.run_in_executor(None, pubsub.unsubscribe, channel)
                await loop.run_in_executor(None, pubsub.close)
                r.close()

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )


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
class SessionResumeView(View):
    """
    Resume a session from history directory and return SSE stream.
    """

    async def post(self, request, session_id):
        """
        Resume an existing Claude session and return SSE stream.
        """
        from django.http import JsonResponse, StreamingHttpResponse
        from asgiref.sync import sync_to_async
        import asyncio

        # Check authentication
        @sync_to_async
        def get_user(request):
            return request.user if request.user.is_authenticated else None

        user = await get_user(request)
        if not user:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        # Get session
        @sync_to_async
        def get_session(session_id):
            return Session.objects.select_related('user').get(id=session_id)

        try:
            session = await get_session(session_id)
        except Session.DoesNotExist:
            return JsonResponse({'error': 'Session not found'}, status=404)

        # Check ownership
        if session.user != user:
            return JsonResponse({'error': 'Access denied'}, status=403)

        # Parse JSON body
        try:
            body = json.loads(request.body)
            history_session_id = body.get('history_session_id')
            message_content = body.get('content', '')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if not history_session_id:
            return JsonResponse({'error': 'history_session_id is required'}, status=400)

        # Add user message if provided
        if message_content:
            @sync_to_async
            def add_messages():
                session.add_message('user', message_content, 'complete')
                session.add_message('agent', '', 'streaming')

            await add_messages()

            await sync_to_async(create_audit_log)(
                event_type='MESSAGE_SENT',
                user_id=user.id,
                session_id=session.id,
                workspace_id=session.workspace_id,
                message_role='user',
                message_summary=message_content[:200],
            )

        # Send resume via WebSocket
        workspace_id = str(session.workspace_id)

        try:
            await send_resume_to_workspace(
                get_channel_layer(),
                workspace_id,
                str(session_id),
                history_session_id,
                message_content,
            )
            logger.info(f'Sent resume to workspace client for session {session_id}')
        except Exception as e:
            logger.error(f'WebSocket resume failed: {e}')
            return JsonResponse({'error': 'Workspace client unavailable'}, status=503)

        # Return SSE stream using async generator with thread-based Redis polling
        async def event_stream():
            session_id_str = str(session_id)
            r = get_redis_client()
            pubsub = r.pubsub()
            channel = f'session:{session_id_str}'
            loop = asyncio.get_running_loop()

            try:
                # Subscribe in thread to avoid blocking
                await loop.run_in_executor(None, pubsub.subscribe, channel)

                # Send initial connection event
                logger.info(f'[SSE] Sending connected event for session {session_id_str}')
                yield f'data: {json.dumps({"type": "connected", "session_id": session_id_str})}\n\n'

                # Poll for messages in thread to avoid blocking event loop
                while True:
                    message = await loop.run_in_executor(None, pubsub.get_message, True, 0.1)

                    if message is None:
                        await asyncio.sleep(0.05)
                        continue

                    if message['type'] == 'message':
                        data = message['data']
                        event = json.loads(data)
                        event_type = event.get('type')

                        logger.info(f'[SSE] Yielding event: type={event_type}, session={session_id_str}')
                        yield f'data: {json.dumps(event)}\n\n'

                        await asyncio.sleep(0)

                        if event_type in ('done', 'error', 'interrupted'):
                            logger.info(f'[SSE] Stream ended for session {session_id_str}')
                            break

            except GeneratorExit:
                logger.info(f'SSE client disconnected for session {session_id_str}')
            finally:
                await loop.run_in_executor(None, pubsub.unsubscribe, channel)
                await loop.run_in_executor(None, pubsub.close)
                r.close()

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
            },
        )