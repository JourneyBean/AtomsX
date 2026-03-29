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
    WorkspaceHistoryListView,
    WorkspaceHistoryMessagesView,
)

urlpatterns = [
    path('', WorkspaceListView.as_view(), name='workspace-list'),
    path('<uuid:workspace_id>/', WorkspaceDetailView.as_view(), name='workspace-detail'),
    # History - more specific route first
    path('<uuid:workspace_id>/history/<str:history_session_id>/',
         WorkspaceHistoryMessagesView.as_view(), name='workspace-history-messages'),
    path('<uuid:workspace_id>/history/', WorkspaceHistoryListView.as_view(), name='workspace-history'),
    # File browser endpoints
    path('<uuid:workspace_id>/tree/', WorkspaceFileTreeView.as_view(), name='workspace-file-tree'),
    re_path(r'^(?P<workspace_id>[0-9a-f-]{36})/files/(?P<file_path>.+)$',
            WorkspaceFileContentView.as_view(), name='workspace-file-content'),
    # Internal API for Workspace Client (uses X-Internal-Token auth)
    path('internal/agent-config/<uuid:workspace_id>/', InternalAgentConfigView.as_view(),
         name='internal-agent-config'),
]