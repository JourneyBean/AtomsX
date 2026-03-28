"""
Celery tasks for Agent message processing.

This module implements:
- Agent message processing with streaming
- Redis pub/sub for SSE push
- File operations in Workspace containers
"""
import logging
import json
import redis
from celery import shared_task
from django.conf import settings
from datetime import datetime
import uuid

from .models import Session
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


def get_redis_client():
    """Get Redis client for pub/sub."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=2,  # Separate DB for SSE channels
        decode_responses=True,
    )


def get_agent_config():
    """
    Get Agent configuration.

    Agent File Operation Boundaries (5.11):
    - Allowed paths: /workspace/src/**, /workspace/public/**
    - Forbidden: /workspace/node_modules/**, /workspace/.git/**
    - Forbidden operations: Deleting critical files, modifying package.json without approval
    """
    return {
        'allowed_paths': ['/workspace/src/', '/workspace/public/', '/workspace/components/'],
        'forbidden_paths': ['/workspace/node_modules/', '/workspace/.git/', '/workspace/.env'],
        'max_file_size': 100 * 1024,  # 100KB max file size
        'allowed_extensions': ['.vue', '.js', '.ts', '.css', '.html', '.json'],
    }


class AgentTaskManager:
    """
    Manages running Agent tasks for interrupt handling.

    In production, this would use Redis to track task state across workers.
    For MVP, we use an in-memory dict with task IDs.
    """

    _tasks = {}  # task_id -> {'stop_requested': bool}

    @classmethod
    def register_task(cls, task_id: str):
        cls._tasks[task_id] = {'stop_requested': False}

    @classmethod
    def request_stop(cls, task_id: str):
        if task_id in cls._tasks:
            cls._tasks[task_id]['stop_requested'] = True

    @classmethod
    def should_stop(cls, task_id: str) -> bool:
        return cls._tasks.get(task_id, {}).get('stop_requested', False)

    @classmethod
    def unregister_task(cls, task_id: str):
        cls._tasks.pop(task_id, None)


def publish_sse_event(session_id: str, event_type: str, data: dict):
    """
    Publish an event to the SSE channel for a session.

    SSE Event Format:
    - type: 'content', 'done', 'error'
    - data: event-specific data
    """
    r = get_redis_client()
    channel = f'session:{session_id}'

    event = json.dumps({
        'type': event_type,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        **data,
    })

    r.publish(channel, event)
    r.close()


@shared_task(bind=True)
def process_agent_message(self, session_id: str, message_id: str, user_message: str):
    """
    Process a user message with the AI Agent.

    This task:
    1. Registers itself for interrupt handling
    2. Streams Agent response chunks to Redis pub/sub
    3. Persists the complete response
    4. Handles interrupts gracefully
    """
    from anthropic import Anthropic

    task_id = self.request.id
    AgentTaskManager.register_task(task_id)

    try:
        session = Session.objects.get(id=session_id)
    except Session.DoesNotExist:
        logger.error(f'Session {session_id} not found')
        return

    r = get_redis_client()

    try:
        # Initialize Anthropic client
        # Note: For MVP, we use direct API. In production, use Claude Agent SDK
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Build conversation history
        messages = []
        for msg in session.messages[:-1]:  # Exclude the last user message (already added)
            messages.append({
                'role': msg['role'],
                'content': msg['content'],
            })

        # Add the current user message
        messages.append({'role': 'user', 'content': user_message})

        # Stream response
        agent_content = ''

        with client.messages.stream(
            model='claude-sonnet-4-20250514',
            max_tokens=4096,
            system='You are a helpful AI assistant helping users build Vue.js applications. You can modify files in the /workspace directory. Always be helpful and provide clear explanations.',
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                # Check for interrupt
                if AgentTaskManager.should_stop(task_id):
                    logger.info(f'Agent task {task_id} interrupted')
                    session.update_message_status(message_id, 'interrupted', agent_content)
                    publish_sse_event(session_id, 'interrupted', {
                        'message': 'Response interrupted',
                        'partial_content': agent_content,
                    })
                    return

                agent_content += text
                publish_sse_event(session_id, 'content', {
                    'content': text,
                    'message_id': message_id,
                })

        # Complete the message
        session.update_message_status(message_id, 'complete', agent_content)

        # Publish done event
        publish_sse_event(session_id, 'done', {
            'message_id': message_id,
            'full_content': agent_content,
        })

        # Audit log
        create_audit_log(
            event_type='AGENT_RESPONSE',
            user_id=session.user_id,
            session_id=session.id,
            workspace_id=session.workspace_id,
            message_role='agent',
            message_summary=agent_content[:200],
        )

        logger.info(f'Agent response completed for session {session_id}')

    except Exception as e:
        logger.exception(f'Agent processing error: {e}')
        session.update_message_status(message_id, 'error', str(e))

        publish_sse_event(session_id, 'error', {
            'message_id': message_id,
            'error': str(e),
        })

        create_audit_log(
            event_type='AGENT_RESPONSE',
            user_id=session.user_id,
            session_id=session.id,
            workspace_id=session.workspace_id,
            error_message=str(e),
        )

    finally:
        AgentTaskManager.unregister_task(task_id)
        r.close()


@shared_task
def interrupt_agent_task(task_id: str, session_id: str, message_id: str):
    """
    Request an interrupt for a running Agent task.
    """
    AgentTaskManager.request_stop(task_id)

    # Also publish interrupt signal to SSE channel
    publish_sse_event(session_id, 'interrupting', {
        'message': 'Interrupt requested',
        'task_id': task_id,
    })

    logger.info(f'Interrupt requested for task {task_id}')
    return {'status': 'interrupt_requested', 'task_id': task_id}