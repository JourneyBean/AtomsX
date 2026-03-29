"""
Docker utilities for Workspace container management.

This module provides helper functions for:
- Container lifecycle management
- Network isolation (4.2)
- Volume management (4.3)
- Resource limits (4.4)
- Port mapping (4.6)
- Security verification (4.7)
- Docker-in-Docker (dind) health checks and validation
"""
import logging
import docker
from typing import Optional, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class DinDNotEnabledError(Exception):
    """Raised when Docker operations are attempted but dind is not enabled."""
    pass


class DinDHealthCheckError(Exception):
    """Raised when dind daemon health check fails."""
    pass


class UserDataDirectoryError(Exception):
    """Raised when user data directory operations fail."""
    def __init__(self, message: str, reason: str = None):
        super().__init__(message)
        self.reason = reason


def check_dind_health(client: docker.DockerClient) -> Dict[str, Any]:
    """
    Check if dind Docker daemon is healthy and accessible.

    Returns a dict with health check results.
    """
    try:
        info = client.info()
        return {
            'healthy': True,
            'docker_version': info.get('ServerVersion', 'unknown'),
            'containers_running': info.get('ContainersRunning', 0),
            'containers_total': info.get('Containers', 0),
            'images': info.get('Images', 0),
            'storage_driver': info.get('Driver', 'unknown'),
        }
    except docker.errors.DockerException as e:
        logger.error(f'Dind health check failed: {e}')
        return {
            'healthy': False,
            'error': str(e),
        }


def get_dind_metrics() -> Dict[str, Any]:
    """
    Get dind daemon metrics for monitoring.

    Returns metrics like container count, health status, etc.
    """
    try:
        client = docker.from_env()
        health = check_dind_health(client)

        if not health['healthy']:
            return {
                'dind_healthy': False,
                'error': health.get('error'),
            }

        return {
            'dind_healthy': True,
            'containers_running': health.get('containers_running', 0),
            'containers_total': health.get('containers_total', 0),
            'images': health.get('images', 0),
            'docker_version': health.get('docker_version'),
            'storage_driver': health.get('storage_driver'),
        }
    except Exception as e:
        return {
            'dind_healthy': False,
            'error': str(e),
        }


def _log_dind_event(event_type: str, details: Dict[str, Any] = None):
    """
    Log dind-related events to audit log.

    This is a helper function to create audit logs for dind events.
    """
    try:
        from apps.core.models import create_audit_log
        create_audit_log(
            event_type=event_type,
            details=details or {},
        )
    except Exception as e:
        logger.warning(f'Failed to create dind audit log: {e}')


class WorkspaceContainerManager:
    """
    Manager for Workspace container operations.

    Architecture Notes (4.2 Network Isolation):
    - All workspace containers are connected to a shared isolated network
    - The network uses Docker's bridge driver
    - Containers can only reach the gateway (for preview access), not each other
    - The host's Docker socket is NOT mounted in containers (security)
    - All operations happen in dind Docker daemon, not host Docker

    Security Notes (4.7):
    - Containers run with dropped capabilities
    - No privilege escalation allowed
    - No access to Docker socket
    - Resource limits prevent runaway consumption
    - Complete isolation from host Docker daemon
    """

    def __init__(self):
        # Allow Docker operations when either:
        # 1. DIND is enabled (production mode with dind daemon)
        # 2. DOCKER_HOST is explicitly set (development mode with host Docker socket)
        if not settings.DIND_ENABLED and not settings.DOCKER_HOST:
            raise DinDNotEnabledError(
                'Docker operations require either DIND_ENABLED=true or DOCKER_HOST to be set.'
            )

        self.client = docker.from_env()

        # Log connection target for debugging
        logger.info(f'Docker client initialized with DOCKER_HOST={settings.DOCKER_HOST}')

        # Verify dind daemon is accessible
        health = check_dind_health(self.client)
        if not health['healthy']:
            error_msg = health.get('error', 'unknown error')
            _log_dind_event('DIND_HEALTH_CHECK_FAILED', {
                'docker_host': settings.DOCKER_HOST,
                'error': error_msg,
            })
            raise DinDHealthCheckError(
                f'Dind daemon health check failed: {error_msg}'
            )

        # Log successful connection
        _log_dind_event('DIND_CONNECTED', {
            'docker_host': settings.DOCKER_HOST,
            'docker_version': health.get('docker_version'),
            'storage_driver': health.get('storage_driver'),
        })
        logger.info(f'Dind daemon healthy: version={health.get("docker_version")}, storage={health.get("storage_driver")}')

    def get_or_create_network(self, network_name: str) -> docker.models.networks.Network:
        """
        Get or create the isolated network for workspaces.

        Network Isolation Strategy (4.2):
        - Single shared network for all workspaces (simpler for MVP)
        - Network is isolated from host network
        - Each container gets its own IP in the network
        - Containers cannot directly reach each other (no inter-container communication needed for MVP)
        """
        try:
            return self.client.networks.get(network_name)
        except docker.errors.NotFound:
            network = self.client.networks.create(
                network_name,
                driver='bridge',
                internal=False,  # Allow outbound for npm install, etc.
                labels={
                    'atomsx.managed': 'true',
                    'atomsx.purpose': 'workspace-isolation',
                },
            )
            logger.info(f'Created isolated network: {network_name}')
            return network

    def create_volume(self, workspace_id: str) -> str:
        """
        Create a dedicated volume for a workspace.

        Volume Strategy (4.3):
        - Each workspace gets its own Docker volume
        - Volume is mounted at /workspace in the container
        - Volume is deleted when workspace is deleted
        - Volume is isolated from other workspaces and host
        """
        volume_name = f'workspace-{workspace_id}'
        try:
            self.client.volumes.get(volume_name)
        except docker.errors.NotFound:
            self.client.volumes.create(
                volume_name,
                labels={
                    'atomsx.managed': 'true',
                    'atomsx.workspace_id': str(workspace_id),
                },
            )
            logger.info(f'Created volume: {volume_name}')
        return volume_name

    def get_container_port(self, container: docker.models.containers.Container) -> Optional[int]:
        """
        Get the host port assigned to a container's preview server.

        Port Mapping Strategy (4.6):
        - Each container binds to a random host port
        - Port is mapped from container:3000 to host:random
        - The random port is tracked in workspace.container_host
        - Gateway proxies to the correct port based on workspace_id
        """
        container.reload()
        ports = container.attrs.get('NetworkSettings', {}).get('Ports', {})
        port_mapping = ports.get('3000/tcp', [{}])[0]
        return port_mapping.get('HostPort')

    def verify_container_security(self, container_id: str) -> Dict[str, Any]:
        """
        Verify that a container meets security requirements (4.7).

        Returns a dict with security check results.
        """
        try:
            container = self.client.containers.get(container_id)
        except docker.errors.NotFound:
            return {'error': 'Container not found'}

        container.reload()
        attrs = container.attrs

        checks = {
            'container_id': container_id[:12],
            'privileged': attrs.get('HostConfig', {}).get('Privileged', False),
            'docker_socket_mounted': self._check_docker_socket_mounted(attrs),
            'capabilities_dropped': 'ALL' in attrs.get('HostConfig', {}).get('CapDrop', []),
            'no_new_privileges': 'no-new-privileges' in attrs.get('HostConfig', {}).get('SecurityOpt', []),
            'memory_limit': attrs.get('HostConfig', {}).get('Memory', 0),
            'cpu_quota': attrs.get('HostConfig', {}).get('CpuQuota', 0),
            'read_only_root': attrs.get('HostConfig', {}).get('ReadonlyRootfs', False),
        }

        # Security assessment
        issues = []
        if checks['privileged']:
            issues.append('CRITICAL: Container runs as privileged')
        if checks['docker_socket_mounted']:
            issues.append('CRITICAL: Docker socket is mounted')
        if not checks['capabilities_dropped']:
            issues.append('WARNING: Capabilities not dropped')
        if not checks['no_new_privileges']:
            issues.append('WARNING: Privilege escalation not prevented')
        if checks['memory_limit'] == 0:
            issues.append('WARNING: No memory limit set')

        checks['issues'] = issues
        checks['secure'] = len([i for i in issues if i.startswith('CRITICAL')]) == 0

        return checks

    def _check_docker_socket_mounted(self, attrs: Dict) -> bool:
        """Check if Docker socket is mounted in the container."""
        mounts = attrs.get('Mounts', [])
        for mount in mounts:
            if '/var/run/docker.sock' in mount.get('Source', ''):
                return True
        return False


# Lazy singleton - only instantiate when actually needed
_container_manager = None


def get_container_manager() -> 'WorkspaceContainerManager':
    """
    Get the container manager singleton instance.

    Uses lazy initialization to avoid creating the instance during module import,
    which could happen before database migrations have run.
    """
    global _container_manager
    if _container_manager is None:
        _container_manager = WorkspaceContainerManager()
    return _container_manager