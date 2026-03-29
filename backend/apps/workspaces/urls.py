"""
URL configuration for Workspaces API.
"""
from django.urls import path, re_path
from .views import (
    WorkspaceListView,
    WorkspaceDetailView,
    WorkspaceFileTreeView,
    WorkspaceFileContentView,
    InternalAgentConfigView,
)

urlpatterns = [
    path('', WorkspaceListView.as_view(), name='workspace-list'),
    path('<uuid:workspace_id>/', WorkspaceDetailView.as_view(), name='workspace-detail'),
    # File browser endpoints
    path('<uuid:workspace_id>/tree/', WorkspaceFileTreeView.as_view(), name='workspace-file-tree'),
    re_path(r'^<uuid:workspace_id>/files/(?P<file_path>.+)$', WorkspaceFileContentView.as_view(), name='workspace-file-content'),
    # Internal API for Workspace Client (uses X-Internal-Token auth)
    path('internal/agent-config/<uuid:workspace_id>/', InternalAgentConfigView.as_view(), name='internal-agent-config'),
]