"""
Celery tasks for Workspace container management.
"""
import logging
import docker
from django.conf import settings
from celery import shared_task
from .models import Workspace
from .docker_utils import check_dind_health, DinDNotEnabledError, DinDHealthCheckError
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


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def create_workspace_container(self, workspace_id: str):
    """
    Create a Docker container for a workspace.

    This task:
    1. Creates a Docker container with the workspace image
    2. Sets up network isolation
    3. Creates a volume for source files
    4. Starts the container
    5. Updates the workspace record with container info
    """
    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        logger.error(f'Workspace {workspace_id} not found')
        return

    # Verify dind is healthy before proceeding
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
            error_message=f'Dind connection error: {e}',
        )
        raise self.retry(exc=e)  # Retry for transient connection issues

    try:
        # Get or create the workspace network
        network_name = settings.WORKSPACE_NETWORK_NAME
        try:
            network = client.networks.get(network_name)
        except docker.errors.NotFound:
            network = client.networks.create(network_name, driver='bridge')
            logger.info(f'Created network: {network_name} in dind')

        # Create volume for workspace files
        volume_name = f'workspace-{workspace_id}'
        try:
            volume = client.volumes.get(volume_name)
        except docker.errors.NotFound:
            volume = client.volumes.create(volume_name)
            logger.info(f'Created volume: {volume_name} in dind')

        # Container configuration
        container_name = f'workspace-{workspace_id}'
        image = settings.WORKSPACE_BASE_IMAGE

        # Check if image exists in dind, build if not
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            logger.warning(f'Image {image} not found in dind')
            # Try to build from workspace-template
            # Note: In dind, we need to copy the template or use a different approach
            # For MVP, we'll pull a base image and set up the workspace manually
            try:
                logger.info(f'Pulling fallback image node:20-slim into dind')
                image = 'node:20-slim'
                client.images.pull(image)
            except docker.errors.DockerException as pull_error:
                logger.error(f'Failed to pull image in dind: {pull_error}')
                raise

        # Create container with security hardening
        container = client.containers.create(
            image=image,
            name=container_name,
            detach=True,
            environment={
                'WORKSPACE_ID': str(workspace_id),
                'NODE_ENV': 'development',
            },
            volumes={
                volume_name: {'bind': '/workspace', 'mode': 'rw'},
            },
            # Use port range 30000-30100 for dind port mapping
            ports={'3000/tcp': None},  # Random port assignment within dind
            network=network_name,
            labels={
                'atomsx.workspace': 'true',
                'atomsx.workspace_id': str(workspace_id),
                'atomsx.owner_id': str(workspace.owner_id),
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
            read_only=False,  # Can't be read-only due to /workspace writes
            privileged=False,  # Never run as privileged
            # No Docker socket mounted - container is fully isolated
        )

        # Start container
        container.start()

        # Get the assigned port from dind
        container.reload()
        ports = container.attrs.get('NetworkSettings', {}).get('Ports', {})
        port_mapping = ports.get('3000/tcp', [{}])[0]
        host_port = port_mapping.get('HostPort')

        # Update workspace record
        workspace.container_id = container.id
        workspace.container_host = f'dind:{host_port}' if host_port else None
        workspace.transition_status('running')
        workspace.save()

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_CREATED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            container_id=container.id,
        )

        logger.info(f'Created container {container.id} for workspace {workspace_id} in dind')

    except DinDHealthCheckError as e:
        logger.error(f'Dind connection error during container creation: {e}')
        workspace.transition_status('error', f'Dind connection error: {e}')
        workspace.save()
        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
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
    3. Removes the volume
    4. Soft-deletes the workspace record
    """
    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        logger.error(f'Workspace {workspace_id} not found')
        return

    if not workspace.container_id:
        logger.warning(f'Workspace {workspace_id} has no container')
        workspace.delete()
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
            error_message=f'Cleanup skipped: Dind not enabled',
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

        # Remove volume from dind
        volume_name = f'workspace-{workspace_id}'
        try:
            volume = client.volumes.get(volume_name)
            volume.remove()
            logger.info(f'Removed volume {volume_name} from dind')
        except docker.errors.NotFound:
            logger.warning(f'Volume {volume_name} not found in dind')

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_DELETED',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
        )

        # Delete workspace record
        workspace.delete()

        logger.info(f'Deleted workspace {workspace_id} from dind')

    except DinDHealthCheckError as e:
        logger.error(f'Dind connection error during container deletion: {e}')
        raise self.retry(exc=e)

    except docker.errors.DockerException as e:
        logger.error(f'Docker operation error in dind: {e}')

        create_audit_log(
            event_type='WORKSPACE_ERROR',
            user_id=workspace.owner_id,
            workspace_id=workspace.id,
            error_message=f'Docker operation error during deletion: {e}',
        )

        # Retry the task
        raise self.retry(exc=e)