"""
Workspace API Views.

Provides REST API endpoints for workspace management:
- POST /api/workspaces/ - Create a new workspace
- GET /api/workspaces/ - List user's workspaces
- GET /api/workspaces/:id/ - Get workspace details
- DELETE /api/workspaces/:id/ - Delete a workspace
"""
import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Workspace
from .serializers import WorkspaceSerializer, CreateWorkspaceSerializer
from .tasks import create_workspace_container, delete_workspace_container
from apps.core.models import create_audit_log

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceListView(APIView):
    """
    API view for listing and creating workspaces.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        List all workspaces owned by the current user.
        """
        workspaces = Workspace.objects.filter(owner=request.user)
        serializer = WorkspaceSerializer(workspaces, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Create a new workspace.
        """
        serializer = CreateWorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']

        # Check for duplicate name
        if Workspace.objects.filter(owner=request.user, name=name).exists():
            return Response(
                {'error': 'Workspace name already exists'},
                status=status.HTTP_409_CONFLICT,
            )

        # Create workspace record
        workspace = Workspace.objects.create(
            owner=request.user,
            name=name,
            status='creating',
        )

        # Trigger async container creation
        create_workspace_container.delay(str(workspace.id))

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_STATUS_CHANGE',
            user_id=request.user.id,
            workspace_id=workspace.id,
            previous_status=None,
            new_status='creating',
        )

        logger.info(f'Created workspace {workspace.id} for user {request.user.id}')

        return Response(
            WorkspaceSerializer(workspace).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name='dispatch')
class WorkspaceDetailView(APIView):
    """
    API view for getting, updating, and deleting a single workspace.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        """
        Get details of a specific workspace.
        """
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = WorkspaceSerializer(workspace)
        return Response(serializer.data)

    def delete(self, request, workspace_id):
        """
        Delete a workspace.
        """
        workspace = get_object_or_404(Workspace, id=workspace_id)

        # Check ownership
        if workspace.owner != request.user:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Update status to deleting
        previous_status = workspace.status
        workspace.transition_status('deleting')
        workspace.save()

        # Audit log
        create_audit_log(
            event_type='WORKSPACE_STATUS_CHANGE',
            user_id=request.user.id,
            workspace_id=workspace.id,
            previous_status=previous_status,
            new_status='deleting',
        )

        # Trigger async container deletion
        delete_workspace_container.delay(str(workspace.id))

        logger.info(f'Deleting workspace {workspace_id}')

        return Response(status=status.HTTP_202_ACCEPTED)