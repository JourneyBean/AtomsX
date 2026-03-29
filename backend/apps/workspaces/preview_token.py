"""
Preview Token utilities for token-based preview authentication.

Tokens are stored in Redis with format:
- Key: preview_token:{token}
- Value: JSON {user_id, workspace_id, created_at}
- TTL: 600 seconds (10 minutes)
"""

import uuid
import json
from datetime import datetime, timezone, timedelta
from django.conf import settings
import redis


# Token TTL in seconds (10 minutes)
PREVIEW_TOKEN_TTL = 600


def get_redis_client():
    """Get Redis client for preview tokens."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=int(settings.REDIS_PORT),
        db=2,  # Use separate DB for tokens
        decode_responses=True,
    )


def generate_preview_token(user_id: str, workspace_id: str) -> dict:
    """
    Generate a new preview token for a workspace.

    Args:
        user_id: UUID string of the user
        workspace_id: UUID string of the workspace

    Returns:
        dict with token, expires_at, workspace_id
    """
    token = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    token_data = {
        'user_id': str(user_id),
        'workspace_id': str(workspace_id),
        'created_at': created_at.isoformat(),
    }

    r = get_redis_client()
    try:
        r.set(
            f'preview_token:{token}',
            json.dumps(token_data),
            ex=PREVIEW_TOKEN_TTL,
        )
    finally:
        r.close()

    expires_at = created_at + timedelta(seconds=PREVIEW_TOKEN_TTL)

    return {
        'token': token,
        'expires_at': expires_at.isoformat(),
        'expires_at_unix': PREVIEW_TOKEN_TTL,  # TTL in seconds for cookie Max-Age
        'workspace_id': str(workspace_id),
        'preview_domain': settings.ATOMSX_PREVIEW_DOMAIN,  # For setting cookie domain
    }


def validate_preview_token(token: str, workspace_id: str) -> dict | None:
    """
    Validate a preview token for a workspace.

    Args:
        token: The preview token string
        workspace_id: Expected workspace UUID string

    Returns:
        dict with user_id, workspace_id if valid, None if invalid
    """
    r = get_redis_client()
    try:
        token_data = r.get(f'preview_token:{token}')

        if not token_data:
            return None

        data = json.loads(token_data)

        # Verify workspace_id matches
        if data.get('workspace_id') != str(workspace_id):
            return None

        return {
            'user_id': data['user_id'],
            'workspace_id': data['workspace_id'],
        }
    finally:
        r.close()