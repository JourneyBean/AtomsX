"""
WebSocket Consumers for Workspace Client connections.

This module handles bidirectional communication between
Backend and Workspace Client containers via WebSocket.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
import redis

from .models import Workspace, WorkspaceToken

logger = logging.getLogger(__name__)


def get_redis_client():
    """Get Redis client for pub/sub."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=2,  # Separate DB for WebSocket channels
        decode_responses=True,
    )


class WorkspaceConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for Workspace Client connections.

    Handles:
    - Token-based authentication
    - Message routing between Backend and Workspace Client
    - Integration with SSE via Redis pub/sub
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace_id = None
        self.workspace_group_name = None
        self.redis_client = None

    async def connect(self):
        """
        Handle WebSocket connection request.

        Validates the token from Authorization header or query parameter and
        accepts connection if valid.
        """
        self.workspace_id = self.scope['url_route']['kwargs']['workspace_id']
        self.workspace_group_name = f'workspace_{self.workspace_id}'

        # Extract token from Authorization header or query parameter
        headers = dict(self.scope['headers'])
        auth_header = headers.get(b'authorization', b'').decode('utf-8')

        # Try Authorization header first
        if auth_header.startswith('Token '):
            token = auth_header[6:]  # Remove 'Token ' prefix
        else:
            # Try query parameter (for workspace-client)
            query_string = self.scope['query_string'].decode('utf-8')
            query_params = dict(p.split('=') for p in query_string.split('&') if '=' in p)
            token = query_params.get('token', '')

        if not token:
            logger.warning(f'No token provided for workspace {self.workspace_id}')
            await self.close(code=4001)
            return

        # Validate token
        if not await self.validate_token(token):
            logger.warning(f'Invalid token for workspace {self.workspace_id}')
            await self.close(code=4001)
            return

        # Join workspace group
        await self.channel_layer.group_add(
            self.workspace_group_name,
            self.channel_name,
        )

        # Accept connection
        await self.accept()

        # Send connection confirmation
        await self.send(json.dumps({
            'type': 'connected',
            'workspace_id': self.workspace_id,
        }))

        logger.info(f'Workspace Client connected: workspace={self.workspace_id}')

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave workspace group
        if self.workspace_group_name:
            await self.channel_layer.group_discard(
                self.workspace_group_name,
                self.channel_name,
            )

        logger.info(f'Workspace Client disconnected: workspace={self.workspace_id}, code={close_code}')

    async def receive(self, text_data):
        """
        Handle incoming message from Workspace Client.

        Routes messages to appropriate handlers and forwards
        to SSE stream via Redis pub/sub.
        """
        try:
            data = json.loads(text_data)
            msg_type = data.get('type')
            session_id = data.get('session_id')

            logger.info(f'Received message from workspace: type={msg_type}, session_id={session_id}')

            if msg_type == 'stream':
                # Forward stream chunks to SSE
                await self.publish_to_sse(session_id, {
                    'type': 'text',
                    'session_id': session_id,
                    'content': data.get('content'),
                })

            elif msg_type == 'tool_use':
                # Forward tool use events to SSE
                await self.publish_to_sse(session_id, {
                    'type': 'tool_use',
                    'session_id': session_id,
                    'tool_name': data.get('tool_name'),
                    'tool_input': data.get('tool_input'),
                })

            elif msg_type == 'started':
                # Session started acknowledgment
                await self.publish_to_sse(session_id, {
                    'type': 'started',
                    'session_id': session_id,
                    'history_session_id': data.get('history_session_id'),
                })

            elif msg_type == 'resumed':
                # Session resumed acknowledgment
                await self.publish_to_sse(session_id, {
                    'type': 'resumed',
                    'session_id': session_id,
                    'history_session_id': data.get('history_session_id'),
                })

            elif msg_type == 'ask_user':
                # Request user input
                await self.publish_to_sse(session_id, {
                    'type': 'ask_user',
                    'session_id': session_id,
                    'request_id': data.get('request_id'),
                    'questions': data.get('questions', []),
                })

            elif msg_type == 'complete':
                # Session completed
                logger.info(f'Session completed: session_id={session_id}')
                await self.publish_to_sse(session_id, {
                    'type': 'done',
                    'session_id': session_id,
                    'response': data.get('response'),
                    'history_session_id': data.get('history_session_id'),
                })

            elif msg_type == 'interrupted':
                # Session was interrupted
                await self.publish_to_sse(session_id, {
                    'type': 'interrupted',
                    'session_id': session_id,
                    'claude_session_id': data.get('claude_session_id'),
                    'partial_content': data.get('partial_content'),
                    'reason': data.get('reason'),
                })

            elif msg_type == 'error':
                # Error occurred
                logger.error(f'Error from workspace client: session_id={session_id}, error={data.get("error")}')
                await self.publish_to_sse(session_id, {
                    'type': 'error',
                    'session_id': session_id,
                    'error': data.get('error'),
                    'error_code': data.get('error_code'),
                    'error_message': data.get('error_message', data.get('error')),
                    'is_recoverable': data.get('is_recoverable', False),
                })

            elif msg_type == 'pong':
                # Heartbeat response
                logger.debug(f'Received pong from workspace {self.workspace_id}')

            elif msg_type == 'ping':
                # Heartbeat request - respond with pong
                await self.send(json.dumps({'type': 'pong'}))

            elif msg_type == 'history_list':
                # History list response from Workspace Client
                request_id = data.get('request_id')
                sessions = data.get('sessions', [])
                logger.info(f'Received history list: request_id={request_id}, sessions={len(sessions)}')

                # Store response in Redis for waiting HTTP request
                if request_id:
                    r = get_redis_client()
                    r.set(
                        f'history_request:{request_id}',
                        json.dumps(sessions),
                        ex=10,  # Expire in 10 seconds
                    )
                    r.close()

            elif msg_type == 'history_messages':
                # History messages response from Workspace Client
                request_id = data.get('request_id')
                messages = data.get('messages', [])
                history_session_id = data.get('history_session_id')
                logger.info(f'Received history messages: request_id={request_id}, history_session_id={history_session_id}, messages={len(messages)}')

                # Store response in Redis for waiting HTTP request
                if request_id:
                    r = get_redis_client()
                    r.set(
                        f'history_messages_request:{request_id}',
                        json.dumps({'messages': messages, 'history_session_id': history_session_id}),
                        ex=10,  # Expire in 10 seconds
                    )
                    r.close()

            else:
                logger.warning(f'Unknown message type: {msg_type}')

        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON received: {e}')
        except Exception as e:
            logger.exception(f'Error processing message: {e}')

    async def task_message(self, event):
        """
        Handle task message from Backend (sent via channel layer).

        This is called when Backend wants to send a task to Workspace Client.
        """
        await self.send(json.dumps({
            'type': 'task',
            'session_id': event.get('session_id'),
            'prompt': event.get('message'),  # Map 'message' to 'prompt' for workspace client
        }))

    async def resume_message(self, event):
        """Handle resume message from Backend."""
        await self.send(json.dumps({
            'type': 'resume',
            'session_id': event.get('session_id'),
            'history_session_id': event.get('history_session_id'),
            'prompt': event.get('prompt'),
        }))

    async def interrupt_message(self, event):
        """Handle interrupt message from Backend."""
        await self.send(json.dumps({
            'type': 'interrupt',
            'session_id': event.get('session_id'),
            'reason': event.get('reason', 'user_requested'),
        }))

    async def user_input_message(self, event):
        """Handle user input message from Backend."""
        await self.send(json.dumps({
            'type': 'user_input',
            'session_id': event.get('session_id'),
            'request_id': event.get('request_id'),
            'input': event.get('input'),
        }))

    async def ping_message(self, event):
        """Handle ping message from Backend."""
        await self.send(json.dumps({
            'type': 'ping',
            'timestamp': event.get('timestamp'),
        }))

    async def history_message(self, event):
        """Handle history request message from Backend."""
        await self.send(json.dumps({
            'type': 'get_history',
            'request_id': event.get('request_id'),
        }))

    async def history_messages_message(self, event):
        """Handle history messages request message from Backend."""
        await self.send(json.dumps({
            'type': 'get_history_messages',
            'request_id': event.get('request_id'),
            'history_session_id': event.get('history_session_id'),
        }))

    @database_sync_to_async
    def validate_token(self, token: str) -> bool:
        """
        Validate the authentication token.

        Returns True if:
        - Token exists in database
        - Token belongs to the workspace in URL
        """
        try:
            workspace_token = WorkspaceToken.objects.get(token=token)
            return str(workspace_token.workspace_id) == self.workspace_id
        except WorkspaceToken.DoesNotExist:
            return False

    async def publish_to_sse(self, session_id: str, data: dict):
        """
        Publish message to SSE stream via Redis pub/sub.

        SSE clients subscribe to session:{session_id} channel
        and receive events from there.
        """
        if not session_id:
            return

        r = get_redis_client()
        channel = f'session:{session_id}'
        r.publish(channel, json.dumps(data))
        r.close()


# Helper functions for Backend to send messages to Workspace Client

async def send_task_to_workspace(channel_layer, workspace_id: str, session_id: str, message: str):
    """Send a task message to a Workspace Client."""
    await channel_layer.group_send(
        f'workspace_{workspace_id}',
        {
            'type': 'task.message',
            'session_id': session_id,
            'message': message,
        }
    )


async def send_resume_to_workspace(
    channel_layer,
    workspace_id: str,
    session_id: str,
    history_session_id: str,
    prompt: str
):
    """Send a resume message to a Workspace Client."""
    await channel_layer.group_send(
        f'workspace_{workspace_id}',
        {
            'type': 'resume.message',
            'session_id': session_id,
            'history_session_id': history_session_id,
            'prompt': prompt,
        }
    )


async def send_interrupt_to_workspace(channel_layer, workspace_id: str, session_id: str):
    """Send an interrupt message to a Workspace Client."""
    await channel_layer.group_send(
        f'workspace_{workspace_id}',
        {
            'type': 'interrupt.message',
            'session_id': session_id,
            'reason': 'user_requested',
        }
    )


async def send_user_input_to_workspace(
    channel_layer,
    workspace_id: str,
    session_id: str,
    request_id: str,
    input_data: dict
):
    """Send user input to a Workspace Client."""
    await channel_layer.group_send(
        f'workspace_{workspace_id}',
        {
            'type': 'user_input.message',
            'session_id': session_id,
            'request_id': request_id,
            'input': input_data,
        }
    )


async def send_get_history_to_workspace(
    channel_layer,
    workspace_id: str,
    request_id: str
):
    """Send a get_history request to a Workspace Client."""
    await channel_layer.group_send(
        f'workspace_{workspace_id}',
        {
            'type': 'history.message',
            'request_id': request_id,
        }
    )


async def send_get_history_messages_to_workspace(
    channel_layer,
    workspace_id: str,
    request_id: str,
    history_session_id: str
):
    """Send a get_history_messages request to a Workspace Client."""
    await channel_layer.group_send(
        f'workspace_{workspace_id}',
        {
            'type': 'history_messages.message',
            'request_id': request_id,
            'history_session_id': history_session_id,
        }
    )