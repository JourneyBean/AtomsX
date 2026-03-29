"""
User data storage utilities for AtomsX Visual Coding Platform.

This module provides utilities for:
- Computing user data directory paths with UUID sharding
- Validating UUID formats
- Managing user data directory structure

Directory Structure:
    {WORKSPACE_DATA_ROOT}/{uuid[0]}/{uuid[1]}/{full_uuid}/
    ├── workspace/    # User code repository
    └── history/      # Conversation history

Sharding Strategy:
    - First-level directory uses first character of UUID (16 directories: 0-9, a-f)
    - Second-level directory uses second character of UUID (16 subdirectories per parent)
    - Full UUID is used as the final directory name
    - Supports up to 256 second-level directories, avoiding single-directory overflow
"""
import os
import uuid
from pathlib import Path
from typing import Optional


class UserDataPathError(Exception):
    """Raised when user data path computation fails."""
    pass


class InvalidUUIDError(UserDataPathError):
    """Raised when UUID format is invalid."""
    pass


def validate_uuid(uuid_str: str) -> uuid.UUID:
    """
    Validate that a string is a valid UUID.

    Args:
        uuid_str: String representation of UUID

    Returns:
        uuid.UUID object if valid

    Raises:
        InvalidUUIDError: If the string is not a valid UUID
    """
    try:
        return uuid.UUID(uuid_str)
    except ValueError as e:
        raise InvalidUUIDError(f"Invalid UUID format: '{uuid_str}'. Error: {e}")


def compute_user_data_path(workspace_uuid: str, root: Optional[str] = None) -> str:
    """
    Compute the user data directory path for a workspace.

    Uses UUID sharding to organize directories:
    - First-level: first character of UUID (a/b/c/.../0-9)
    - Second-level: second character of UUID
    - Final: full UUID as directory name

    Args:
        workspace_uuid: UUID string for the workspace
        root: Root directory path. If None, uses settings.WORKSPACE_DATA_ROOT

    Returns:
        Absolute path to user data directory

    Raises:
        InvalidUUIDError: If UUID format is invalid

    Example:
        >>> compute_user_data_path('abc12345-def6-7890-abcd-ef1234567890', '/var/opt/atomsx')
        '/var/opt/atomsx/a/b/abc12345-def6-7890-abcd-ef1234567890'
    """
    # Validate UUID
    validate_uuid(workspace_uuid)

    # Get root from settings if not provided
    if root is None:
        from django.conf import settings
        root = settings.WORKSPACE_DATA_ROOT

    # Normalize root path
    root_path = Path(root).resolve()

    # Extract first and second characters for sharding
    uuid_lower = workspace_uuid.lower()
    first_char = uuid_lower[0]
    second_char = uuid_lower[1]

    # Build sharded path
    data_path = root_path / first_char / second_char / uuid_lower

    return str(data_path)


def get_workspace_subdir_path(data_dir_path: str, subdir: str) -> str:
    """
    Get the path to a specific subdirectory within user data directory.

    Args:
        data_dir_path: Base user data directory path
        subdir: Subdirectory name ('workspace' or 'history')

    Returns:
        Path to the subdirectory

    Raises:
        UserDataPathError: If subdir is not valid
    """
    valid_subdirs = ['workspace', 'history']
    if subdir not in valid_subdirs:
        raise UserDataPathError(
            f"Invalid subdirectory: '{subdir}'. Must be one of: {valid_subdirs}"
        )

    return os.path.join(data_dir_path, subdir)


def create_user_data_directory(data_dir_path: str) -> dict:
    """
    Create user data directory with required subdirectories.

    Creates directories owned by uid=1000:gid=1000 (the workspace container user)
    to ensure the container can write to the mounted volume.

    Args:
        data_dir_path: Path to user data directory

    Returns:
        Dict with created paths and status

    Raises:
        OSError: If directory creation fails (permission denied, disk full, etc.)
    """
    workspace_path = get_workspace_subdir_path(data_dir_path, 'workspace')
    history_path = get_workspace_subdir_path(data_dir_path, 'history')

    # Create directories with mode 0755
    os.makedirs(data_dir_path, mode=0o755, exist_ok=True)
    os.makedirs(workspace_path, mode=0o755, exist_ok=True)
    os.makedirs(history_path, mode=0o755, exist_ok=True)

    # Set ownership to uid=1000:gid=1000 (workspace container user)
    # This ensures the container can write to the mounted volume
    CONTAINER_USER_UID = 1000
    CONTAINER_USER_GID = 1000

    os.chown(data_dir_path, CONTAINER_USER_UID, CONTAINER_USER_GID)
    os.chown(workspace_path, CONTAINER_USER_UID, CONTAINER_USER_GID)
    os.chown(history_path, CONTAINER_USER_UID, CONTAINER_USER_GID)

    return {
        'data_dir': data_dir_path,
        'workspace_dir': workspace_path,
        'history_dir': history_path,
        'created': True,
    }