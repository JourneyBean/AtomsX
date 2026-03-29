"""
Django management command to prebuild workspace images.

This command prebuilds workspace images and stores them in the Docker registry
(dind or host Docker) for faster workspace creation.

Supports two modes:
- --build: Build from Dockerfile at workspace-templates/ubuntu-24.04/
- --pull-base: Pull base image only (for development/debugging)
"""

import logging
import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import docker

from apps.workspaces.docker_utils import (
    check_dind_health,
    DinDNotEnabledError,
    DinDHealthCheckError,
)
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Prebuild workspace images and store them in Docker registry for faster workspace creation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--image',
            type=str,
            default=None,
            help='Custom image name to build/pull (e.g., custom-workspace:v1). Default: WORKSPACE_BASE_IMAGE setting',
        )
        parser.add_argument(
            '--build',
            action='store_true',
            help='Build from Dockerfile at workspace-templates/ubuntu-24.04/ instead of pulling',
        )
        parser.add_argument(
            '--pull-base',
            action='store_true',
            help='Pull base image only (for development/debugging, no workspace-client)',
        )
        parser.add_argument(
            '--dockerfile-path',
            type=str,
            default=None,
            help='Custom path to Dockerfile directory. Default: workspace-templates/ubuntu-24.04/',
        )
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='Do not use cache when building the image',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force rebuild even if image already exists',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed build/pull progress',
        )

    def handle(self, *args, **options):
        image_name = options['image'] or settings.WORKSPACE_BASE_IMAGE
        force = options['force']
        verbose = options['verbose']
        no_cache = options['no_cache']
        do_build = options['build']
        pull_base = options['pull_base']
        dockerfile_path = options['dockerfile_path']

        # Default mode: build
        if not do_build and not pull_base:
            do_build = True

        self.stdout.write(f'Prebuilding workspace image: {image_name}')
        self.stdout.write(f'Mode: {"build" if do_build else "pull-base"}')

        if verbose:
            self.stdout.write(f'DIND_ENABLED: {settings.DIND_ENABLED}')
            self.stdout.write(f'DOCKER_HOST: {settings.DOCKER_HOST}')

        # Check Docker daemon availability
        try:
            if not settings.DIND_ENABLED and not settings.DOCKER_HOST:
                raise CommandError(
                    'Docker operations require either DIND_ENABLED=true or DOCKER_HOST to be set.'
                )

            client = docker.from_env()

            # Health check
            health = check_dind_health(client)
            if not health['healthy']:
                raise CommandError(
                    f'Docker daemon health check failed: {health.get("error", "unknown error")}'
                )

            if verbose:
                self.stdout.write(f'Docker version: {health.get("docker_version", "unknown")}')
                self.stdout.write(f'Storage driver: {health.get("storage_driver", "unknown")}')

        except DinDNotEnabledError as e:
            raise CommandError(f'Docker not enabled: {e}')
        except DinDHealthCheckError as e:
            raise CommandError(f'Docker daemon health check failed: {e}')
        except docker.errors.DockerException as e:
            raise CommandError(f'Docker daemon unavailable: {e}')

        # Check if image exists
        image_exists = False
        try:
            client.images.get(image_name)
            image_exists = True
            if verbose:
                self.stdout.write(f'Image {image_name} already exists in registry')
        except docker.errors.ImageNotFound:
            if verbose:
                self.stdout.write(f'Image {image_name} not found in registry')

        # Force rebuild: remove existing image
        if force and image_exists:
            self.stdout.write(f'Force rebuild: removing existing image {image_name}')
            try:
                client.images.remove(image_name, force=True)
                image_exists = False
            except docker.errors.DockerException as e:
                raise CommandError(f'Failed to remove existing image: {e}')

        # Build or pull image
        if not image_exists:
            if do_build:
                # Build from Dockerfile
                self._build_image(client, image_name, dockerfile_path, no_cache, verbose)
            elif pull_base:
                # Pull base image only
                self._pull_base_image(client, image_name, verbose)
        else:
            self.stdout.write(f'Image {image_name} already exists, skipping build/pull')

        # Get image details
        try:
            image = client.images.get(image_name)
            image_size = image.attrs.get('Size', 0)
            image_id = image.id[:12]

            if verbose:
                self.stdout.write(f'Image ID: {image_id}')
                self.stdout.write(f'Image size: {image_size / (1024 * 1024):.2f} MB')

            # Audit log for successful prebuild
            create_audit_log(
                event_type='IMAGE_PREBUILD',
                details={
                    'image_name': image_name,
                    'image_id': image_id,
                    'image_size': image_size,
                    'success': True,
                    'force_rebuild': force,
                    'mode': 'build' if do_build else 'pull_base',
                },
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Image prebuild complete: {image_name} ({image_size / (1024 * 1024):.2f} MB)'
                )
            )

        except docker.errors.DockerException as e:
            # Audit log for failed prebuild
            create_audit_log(
                event_type='IMAGE_PREBUILD',
                details={
                    'image_name': image_name,
                    'success': False,
                    'error_message': str(e),
                },
            )
            raise CommandError(f'Failed to get image details: {e}')

    def _build_image(self, client, image_name: str, dockerfile_path: str = None,
                       no_cache: bool = False, verbose: bool = False):
        """Build image from Dockerfile."""
        # Determine Dockerfile path
        if dockerfile_path:
            build_path = Path(dockerfile_path)
        else:
            # Check common locations
            # 1. /workspace-templates (mounted in dev)
            # 2. {project_root}/workspace-templates (relative to backend)
            candidates = [
                Path('/workspace-templates/ubuntu-24.04'),
                Path(settings.BASE_DIR).parent / 'workspace-templates' / 'ubuntu-24.04',
            ]

            build_path = None
            for candidate in candidates:
                if candidate.exists():
                    build_path = candidate
                    break

            if build_path is None:
                raise CommandError(
                    f'Dockerfile path not found. Searched:\n'
                    + '\n'.join(f'  - {c}' for c in candidates)
                    + '\n\nPlease ensure workspace-templates is mounted or use --dockerfile-path'
                )

        if not build_path.exists():
            raise CommandError(f'Dockerfile path not found: {build_path}')

        dockerfile = build_path / 'Dockerfile'
        if not dockerfile.exists():
            raise CommandError(f'Dockerfile not found: {dockerfile}')

        self.stdout.write(f'Building from: {build_path}')
        self.stdout.write(f'Dockerfile: {dockerfile}')

        try:
            # Build the image
            self.stdout.write('Starting build...')

            build_output = client.api.build(
                path=str(build_path),
                tag=image_name,
                rm=True,  # Remove intermediate containers
                decode=True,  # Always decode to get dict
                nocache=no_cache,  # Don't use cache if specified
            )

            for chunk in build_output:
                if verbose and 'stream' in chunk:
                    self.stdout.write(chunk['stream'].strip())
                elif 'error' in chunk:
                    raise CommandError(f'Build error: {chunk["error"]}')

            self.stdout.write(self.style.SUCCESS(f'Successfully built image: {image_name}'))

        except docker.errors.DockerException as e:
            raise CommandError(f'Failed to build image: {e}')

    def _pull_base_image(self, client, image_name: str, verbose: bool = False):
        """Pull base image only (for development)."""
        self.stdout.write(f'Pulling base image: {image_name}')
        try:
            image = client.images.pull(image_name)
            self.stdout.write(self.style.SUCCESS(f'Successfully pulled image: {image_name}'))
        except docker.errors.DockerException as e:
            # Fallback: try node:20-slim
            self.stdout.write(f'Failed to pull {image_name}, trying fallback: node:20-slim')
            try:
                fallback_image = 'node:20-slim'
                image = client.images.pull(fallback_image)
                image.tag(image_name, tag='latest')
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully pulled fallback image and tagged as: {image_name}')
                )
            except docker.errors.DockerException as fallback_error:
                raise CommandError(f'Failed to pull fallback image: {fallback_error}')