"""
Celery tasks for Workspace container management.
"""
import os
import logging
import docker
from django.conf import settings
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from .models import Workspace, WorkspaceToken
from .docker_utils import check_dind_health, DinDNotEnabledError, DinDHealthCheckError, UserDataDirectoryError
from .data_utils import compute_user_data_path, create_user_data_directory
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


def get_docker_client():
    """
    Get a Docker client instance with dind validation.
    """
    # Allow Docker operations when either:
    # 1. DIND is enabled (production mode with dind daemon)
    # 2. DOCKER_HOST is explicitly set (development mode with host Docker socket)
    if not settings.DIND_ENABLED and not settings.DOCKER_HOST:
        raise DinDNotEnabledError(
            'Docker operations require either DIND_ENABLED=true or DOCKER_HOST to be set.'
        )

    client = docker.from_env()

    # Quick health check before returning client
    health = check_dind_health(client)
    if not health['healthy']:
        raise DinDHealthCheckError(
            f'Dind daemon health check failed: {health.get("error", "unknown error")}'
        )

    return client


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=settings.WORKSPACE_CREATION_SOFT_TIMEOUT,
    time_limit=settings.WORKSPACE_CREATION_HARD_TIMEOUT,
)
def create_workspace_container(self, workspace_id: str):
    """
    Create a Docker container for a workspace.

    This task:
    1. Creates user data directory with UUID sharding
    2. Creates a Docker container with the workspace image
    3. Sets up network isolation
    4. Mounts user data directory as /home/user
    5. Starts the container
    6. Updates the workspace record with container info

    Timeout: Configurable via WORKSPACE_CREATION_SOFT_TIMEOUT and WORKSPACE_CREATION_HARD_TIMEOUT
    """
    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        logger.error(f'Workspace {workspace_id} not found')
        return

    # Handle soft timeout exception
    try:
        # Step 1: Create user data directory first
        data_dir_path = None
        bind_mount_path = None
        try:
            # Compute data directory path (internal path for Celery worker)
            data_dir_path = compute_user_data_path(str(workspace.id))

            # Compute bind mount path (host path for Docker)
            # In dind mode, these are the same; in dev mode with host Docker socket, they differ
            bind_mount_path = compute_user_data_path(
                str(workspace.id),
                root=settings.HOST_WORKSPACE_DATA_ROOT
            )

            # Check if directory already exists (reuse case)
            if os.path.exists(data_dir_path):
                logger.info(f'Data directory already exists for workspace {workspace_id}: {data_dir_path}')
            else:
                # Create directory structure
                result = create_user_data_directory(data_dir_path)
                logger.info(f'Created user data directory for workspace {workspace_id}: {data_dir_path}')

            # Update workspace record with data directory path
            workspace.data_dir_path = data_dir_path
            workspace.save(update_fields=['data_dir_path'])

        except PermissionError as e:
            error_msg = f'Failed to create data directory: permission denied - {e}'
            logger.error(error_msg)
            workspace.transition_status('error', error_msg)
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=error_msg,
            )
            raise UserDataDirectoryError(error_msg, reason='permission_denied')

        except OSError as e:
            # Handle disk full and other OS errors
            if 'No space left on device' in str(e) or e.errno == 28:  # ENOSPC
                error_msg = 'Failed to create data directory: disk full'
            else:
                error_msg = f'Failed to create data directory: {e}'

            logger.error(error_msg)
            workspace.transition_status('error', error_msg)
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=error_msg,
            )
            raise UserDataDirectoryError(error_msg, reason='os_error')

        # Step 2: Verify dind is healthy before proceeding
        try:
            client = get_docker_client()
        except DinDNotEnabledError as e:
            logger.error(f'Dind not enabled: {e}')
            workspace.transition_status('error', 'Docker-in-Docker not enabled')
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=f'Dind configuration error: {e}',
            )
            return  # Don't retry configuration errors
        except DinDHealthCheckError as e:
            logger.error(f'Dind health check failed: {e}')
            workspace.transition_status('error', 'Docker daemon unavailable')
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=f'Dind connection error: {e}',
            )
            raise self.retry(exc=e)  # Retry for transient connection issues

        # Get or create the workspace network
        network_name = settings.WORKSPACE_NETWORK_NAME
        try:
            network = client.networks.get(network_name)
        except docker.errors.NotFound:
            network = client.networks.create(network_name, driver='bridge')
            logger.info(f'Created network: {network_name} in dind')

        # Create auth token for Workspace Client WebSocket connection
        workspace_token = WorkspaceToken.create_for_workspace(workspace)
        logger.info(f'Created auth token for workspace {workspace_id}')

        # Container configuration
        container_name = f'workspace-{workspace_id}'
        base_image = settings.WORKSPACE_BASE_IMAGE
        image_source = 'unknown'

        # Check if prebuilt image exists in dind
        try:
            client.images.get(base_image)
            image = base_image
            image_source = 'prebuilt'
            logger.info(f'Using prebuilt image: {base_image}')
        except docker.errors.ImageNotFound:
            logger.error(f'Prebuilt image {base_image} not found in dind')
            error_msg = (
                f'Workspace image not found: {base_image}. '
                'Please run: python manage.py prebuild_workspace_images --build'
            )
            workspace.transition_status('error', error_msg)
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=error_msg,
            )
            return

        # Create container with security hardening and bind mounts for workspace and history
        # Mount workspace and history directories separately (not entire /home/user)
        # Use HOST_WORKSPACE_DATA_ROOT for bind mount source paths
        host_workspace_path = os.path.join(bind_mount_path, 'workspace')
        host_history_path = os.path.join(bind_mount_path, 'history')

        container = client.containers.create(
            image=image,
            name=container_name,
            detach=True,
            environment={
                'WORKSPACE_ID': str(workspace_id),
                'NODE_ENV': 'development',
                # Workspace Client authentication
                'ATOMSX_AUTH_TOKEN': workspace_token.token,
                'ATOMSX_BACKEND_WS_URL': settings.WORKSPACE_CLIENT_WS_URL,
                'ATOMSX_BACKEND_HTTP_URL': settings.WORKSPACE_CLIENT_HTTP_URL,
                'ATOMSX_INTERNAL_API_TOKEN': settings.INTERNAL_API_TOKEN,
            },
            # Mount workspace and history directories separately
            volumes={
                host_workspace_path: {'bind': '/home/user/workspace', 'mode': 'rw'},
                host_history_path: {'bind': '/home/user/history', 'mode': 'rw'},
            },
            # No port mapping needed - Gateway accesses containers via Docker DNS
            network=network_name,
            labels={
                'atomsx.workspace': 'true',
                'atomsx.workspace_id': str(workspace_id),
                'atomsx.owner_id': str(workspace.owner_id),
                'atomsx.data_dir_path': data_dir_path,
            },
            # Resource limits (4.4)
            mem_limit='512m',
            memswap_limit='512m',  # Disable swap
            cpu_period=100000,
            cpu_quota=50000,  # 50% CPU
            # Security hardening (4.7)
            security_opt=['no-new-privileges'],  # Prevent privilege escalation
            cap_drop=['ALL'],  # Drop all Linux capabilities
            cap_add=['CHOWN', 'SETUID', 'SETGID'],  # Only add necessary ones
            read_only=False,  # Can't be read-only due to writes
            privileged=False,  # Never run as privileged
            # No Docker socket mounted - container is fully isolated
        )

        # Start container
        container.start()

        # Update workspace record
        # container_host uses Docker DNS format: workspace-{uuid}:3000
        # Gateway can resolve this via Docker DNS when on the same network
        workspace.container_id = container.id
        workspace.container_host = f'workspace-{workspace_id}:3000'
        workspace.data_dir_path = data_dir_path
        workspace.transition_status('running')
        workspace.save()

        # Audit log with image source and data directory path
        create_audit_log(
            event_type='WORKSPACE_CREATED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            container_id=container.id,
            details={'data_dir_path': data_dir_path, 'image_source': image_source},
        )

        logger.info(f'Created container {container.id} for workspace {workspace_id} in dind (image_source: {image_source}, data_dir: {data_dir_path})')

    except SoftTimeLimitExceeded:
        logger.error(f'Workspace creation exceeded soft time limit ({settings.WORKSPACE_CREATION_SOFT_TIMEOUT}s)')
        workspace.transition_status(
            'error',
            f'Workspace creation timeout exceeded (soft limit: {settings.WORKSPACE_CREATION_SOFT_TIMEOUT}s)'
        )
        workspace.save()
        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': workspace.data_dir_path},
            error_message=f'timeout (soft limit: {settings.WORKSPACE_CREATION_SOFT_TIMEOUT}s)',
        )
        return  # Don't retry timeout errors

    except DinDHealthCheckError as e:
        logger.error(f'Dind connection error during container creation: {e}')
        workspace.transition_status('error', f'Dind connection error: {e}')
        workspace.save()
        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': workspace.data_dir_path},
            error_message=f'Dind connection error: {e}',
        )
        raise self.retry(exc=e)

    except docker.errors.DockerException as e:
        logger.error(f'Docker operation error in dind: {e}')
        workspace.transition_status('error', f'Docker error: {e}')
        workspace.save()

        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': workspace.data_dir_path},
            error_message=f'Docker operation error: {e}',
        )

        # Retry the task for operational errors
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def delete_workspace_container(self, workspace_id: str):
    """
    Delete the Docker container for a workspace.

    This task:
    1. Stops the container
    2. Removes the container
    3. Preserves user data directory on host
    4. Deletes the workspace record

    Note: User data directory is NOT deleted to allow for data recovery and reuse.
    """
    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        logger.error(f'Workspace {workspace_id} not found')
        return

    data_dir_path = workspace.data_dir_path

    if not workspace.container_id:
        logger.warning(f'Workspace {workspace_id} has no container')
        workspace.delete()
        create_audit_log(
            event_type='WORKSPACE_DELETED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': data_dir_path, 'note': 'Container not found, data directory preserved'},
        )
        return

    # Verify dind is healthy before proceeding
    try:
        client = get_docker_client()
    except DinDNotEnabledError as e:
        logger.error(f'Dind not enabled: {e}')
        # Mark as deleted anyway since we can't clean up
        workspace.delete()
        create_audit_log(
            event_type='WORKSPACE_DELETED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': data_dir_path, 'note': 'Cleanup skipped: Dind not enabled, data directory preserved'},
        )
        return
    except DinDHealthCheckError as e:
        logger.error(f'Dind health check failed: {e}')
        raise self.retry(exc=e)  # Retry for transient connection issues

    try:
        # Get container from dind
        try:
            container = client.containers.get(workspace.container_id)
        except docker.errors.NotFound:
            logger.warning(f'Container {workspace.container_id} not found in dind')
            container = None

        if container:
            # Stop container
            container.stop(timeout=10)
            logger.info(f'Stopped container {workspace.container_id} in dind')

            # Remove container
            container.remove()
            logger.info(f'Removed container {workspace.container_id} from dind')

        # Delete the workspace auth token (cleanup)
        try:
            if hasattr(workspace, 'auth_token') and workspace.auth_token:
                workspace.auth_token.delete()
                logger.info(f'Deleted auth token for workspace {workspace_id}')
        except Exception as e:
            logger.warning(f'Failed to delete auth token for workspace {workspace_id}: {e}')

        # Note: We do NOT remove the user data directory
        # Data persists on host filesystem for recovery/reuse
        if data_dir_path:
            logger.info(f'Data directory preserved at: {data_dir_path}')

        # Audit log - container deleted, data preserved
        create_audit_log(
            event_type='WORKSPACE_DELETED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': data_dir_path, 'note': 'Container deleted, data directory preserved on host'},
        )

        # Delete workspace record
        workspace.delete()

        logger.info(f'Deleted workspace {workspace_id} from dind (data preserved at: {data_dir_path})')

    except DinDHealthCheckError as e:
        logger.error(f'Dind connection error during container deletion: {e}')
        raise self.retry(exc=e)

    except docker.errors.DockerException as e:
        logger.error(f'Docker operation error in dind: {e}')

        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': data_dir_path},
            error_message=f'Docker operation error during deletion: {e}',
        )

        # Retry the task
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=settings.WORKSPACE_CREATION_SOFT_TIMEOUT,
    time_limit=settings.WORKSPACE_CREATION_HARD_TIMEOUT,
)
def recreate_workspace_container(self, workspace_id: str):
    """
    Recreate a Docker container for a workspace with the latest image.

    This task:
    1. Stops and removes old container (if exists)
    2. Deletes old WorkspaceToken
    3. Creates new WorkspaceToken
    4. Creates a new container with the same data_dir_path
    5. Starts the container
    6. Updates the workspace record with new container info

    The data directory (workspace + history) is preserved.
    """
    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        logger.error(f'Workspace {workspace_id} not found')
        return

    old_container_id = workspace.container_id
    data_dir_path = workspace.data_dir_path

    # Handle soft timeout exception
    try:
        # Step 1: Verify dind is healthy
        try:
            client = get_docker_client()
        except DinDNotEnabledError as e:
            logger.error(f'Dind not enabled: {e}')
            workspace.transition_status('error', 'Docker-in-Docker not enabled')
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=f'Dind configuration error: {e}',
            )
            return  # Don't retry configuration errors
        except DinDHealthCheckError as e:
            logger.error(f'Dind health check failed: {e}')
            workspace.transition_status('error', 'Docker daemon unavailable')
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path},
                error_message=f'Dind connection error: {e}',
            )
            raise self.retry(exc=e)  # Retry for transient connection issues

        # Step 2: Stop and remove old container (if exists)
        if old_container_id:
            try:
                old_container = client.containers.get(old_container_id)
                # Stop container with timeout
                old_container.stop(timeout=10)
                logger.info(f'Stopped old container {old_container_id} for workspace {workspace_id}')
                # Remove container
                old_container.remove()
                logger.info(f'Removed old container {old_container_id} for workspace {workspace_id}')
            except docker.errors.NotFound:
                logger.warning(f'Old container {old_container_id} not found in dind, proceeding with recreate')
            except docker.errors.DockerException as e:
                logger.error(f'Error removing old container: {e}')
                # Continue anyway - we can still create new container

        # Step 3: Delete old WorkspaceToken
        try:
            if hasattr(workspace, 'auth_token') and workspace.auth_token:
                workspace.auth_token.delete()
                logger.info(f'Deleted old auth token for workspace {workspace_id}')
        except Exception as e:
            logger.warning(f'Failed to delete old auth token for workspace {workspace_id}: {e}')

        # Step 4: Get or create the workspace network
        network_name = settings.WORKSPACE_NETWORK_NAME
        try:
            network = client.networks.get(network_name)
        except docker.errors.NotFound:
            network = client.networks.create(network_name, driver='bridge')
            logger.info(f'Created network: {network_name} in dind')

        # Step 5: Create new WorkspaceToken
        workspace_token = WorkspaceToken.create_for_workspace(workspace)
        logger.info(f'Created new auth token for workspace {workspace_id}')

        # Step 6: Create new container
        container_name = f'workspace-{workspace_id}'
        base_image = settings.WORKSPACE_BASE_IMAGE

        # Check if prebuilt image exists
        try:
            client.images.get(base_image)
            image = base_image
            logger.info(f'Using prebuilt image: {base_image}')
        except docker.errors.ImageNotFound:
            logger.error(f'Prebuilt image {base_image} not found in dind')
            error_msg = (
                f'Workspace image not found: {base_image}. '
                'Please run: python manage.py prebuild_workspace_images --build'
            )
            workspace.transition_status('error', error_msg)
            workspace.save()
            create_audit_log(
                event_type='WORKSPACE_ERROR',
                user_id=workspace.owner_id,
                workspace_id=workspace.id,
                details={'data_dir_path': data_dir_path, 'old_container_id': old_container_id},
                error_message=error_msg,
            )
            return

        # Compute bind mount path
        bind_mount_path = compute_user_data_path(
            str(workspace.id),
            root=settings.HOST_WORKSPACE_DATA_ROOT
        ) if settings.HOST_WORKSPACE_DATA_ROOT else data_dir_path

        # Mount paths
        host_workspace_path = os.path.join(bind_mount_path, 'workspace')
        host_history_path = os.path.join(bind_mount_path, 'history')

        container = client.containers.create(
            image=image,
            name=container_name,
            detach=True,
            environment={
                'WORKSPACE_ID': str(workspace_id),
                'NODE_ENV': 'development',
                # Workspace Client authentication
                'ATOMSX_AUTH_TOKEN': workspace_token.token,
                'ATOMSX_BACKEND_WS_URL': settings.WORKSPACE_CLIENT_WS_URL,
                'ATOMSX_BACKEND_HTTP_URL': settings.WORKSPACE_CLIENT_HTTP_URL,
            },
            # Mount workspace and history directories separately
            volumes={
                host_workspace_path: {'bind': '/home/user/workspace', 'mode': 'rw'},
                host_history_path: {'bind': '/home/user/history', 'mode': 'rw'},
            },
            ports={'3000/tcp': None},  # Random port assignment within dind
            network=network_name,
            labels={
                'atomsx.workspace': 'true',
                'atomsx.workspace_id': str(workspace_id),
                'atomsx.owner_id': str(workspace.owner_id),
                'atomsx.data_dir_path': data_dir_path or '',
            },
            # Resource limits
            mem_limit='512m',
            memswap_limit='512m',
            cpu_period=100000,
            cpu_quota=50000,  # 50% CPU
            # Security hardening
            security_opt=['no-new-privileges'],
            cap_drop=['ALL'],
            cap_add=['CHOWN', 'SETUID', 'SETGID'],
            read_only=False,
            privileged=False,
        )

        # Step 7: Start container
        container.start()

        # Get the assigned port from dind
        container.reload()
        ports = container.attrs.get('NetworkSettings', {}).get('Ports', {})
        port_mapping = ports.get('3000/tcp', [{}])[0]
        host_port = port_mapping.get('HostPort')

        # Step 8: Update workspace record
        workspace.container_id = container.id
        # container_host uses Docker DNS format: gateway can resolve workspace-{uuid}
        workspace.container_host = f'workspace-{workspace_id}:3000'
        workspace.transition_status('running')
        workspace.save()

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_RECREATED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            container_id=container.id,
            details={
                'data_dir_path': data_dir_path,
                'old_container_id': old_container_id,
                'new_container_id': container.id,
            },
        )

        logger.info(f'Recreated container {container.id} for workspace {workspace_id} (old: {old_container_id}, data: {data_dir_path})')

    except SoftTimeLimitExceeded:
        logger.error(f'Workspace recreate exceeded soft time limit ({settings.WORKSPACE_CREATION_SOFT_TIMEOUT}s)')
        workspace.transition_status(
            'error',
            f'Workspace recreate timeout exceeded (soft limit: {settings.WORKSPACE_CREATION_SOFT_TIMEOUT}s)'
        )
        workspace.save()
        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': workspace.data_dir_path, 'old_container_id': old_container_id},
            error_message=f'recreate timeout (soft limit: {settings.WORKSPACE_CREATION_SOFT_TIMEOUT}s)',
        )
        return  # Don't retry timeout errors

    except DinDHealthCheckError as e:
        logger.error(f'Dind connection error during container recreate: {e}')
        workspace.transition_status('error', f'Dind connection error: {e}')
        workspace.save()
        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': workspace.data_dir_path, 'old_container_id': old_container_id},
            error_message=f'Dind connection error: {e}',
        )
        raise self.retry(exc=e)

    except docker.errors.DockerException as e:
        logger.error(f'Docker operation error during recreate: {e}')
        workspace.transition_status('error', f'Docker error: {e}')
        workspace.save()

        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            details={'data_dir_path': workspace.data_dir_path, 'old_container_id': old_container_id},
            error_message=f'Docker operation error during recreate: {e}',
        )

        # Retry the task for operational errors
        raise self.retry(exc=e)


@shared_task
def cleanup_workspace_token(workspace_id: str):
    """
    Delete the WorkspaceToken for a workspace.

    Used when a container stops unexpectedly or for manual cleanup.
    """
    try:
        workspace = Workspace.objects.get(id=workspace_id)
        if hasattr(workspace, 'auth_token') and workspace.auth_token:
            workspace.auth_token.delete()
            logger.info(f'Cleaned up auth token for workspace {workspace_id}')
            return True
    except Workspace.DoesNotExist:
        logger.warning(f'Workspace {workspace_id} not found for token cleanup')
    except Exception as e:
        logger.error(f'Failed to cleanup token for workspace {workspace_id}: {e}')
    return False


@shared_task
def cleanup_orphaned_tokens():
    """
    Periodic task to clean up orphaned WorkspaceTokens.

    Orphaned tokens occur when:
    - Container crashes unexpectedly
    - Workspace status is not 'running' but token still exists
    - Container was manually removed outside the system

    This task checks for tokens where:
    - Workspace status is not 'running'
    - OR workspace has no container_id

    And deletes them to maintain security.
    """
    # Find tokens for workspaces that are not running
    orphaned_tokens = WorkspaceToken.objects.filter(
        workspace__status__in=['stopped', 'error', 'deleting']
    ) | WorkspaceToken.objects.filter(
        workspace__container_id__isnull=True
    )

    # Exclude creating status (token might be just created)
    orphaned_tokens = orphaned_tokens.exclude(
        workspace__status='creating'
    )

    count = orphaned_tokens.count()
    if count > 0:
        for token in orphaned_tokens:
            logger.info(
                f'Deleting orphaned token for workspace {token.workspace.id} '
                f'(status: {token.workspace.status}, container: {token.workspace.container_id})'
            )
            token.delete()

        logger.info(f'Cleaned up {count} orphaned workspace tokens')
        create_audit_log(
            event_type='TOKEN_CLEANUP',
            details={'count': count, 'reason': 'orphaned_tokens'},
        )

    return count