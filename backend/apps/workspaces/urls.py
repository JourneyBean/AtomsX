"""
URL configuration for Workspaces API.
"""
from django.urls import path
from .views import WorkspaceListView, WorkspaceDetailView

urlpatterns = [
    path('', WorkspaceListView.as_view(), name='workspace-list'),
    path('<uuid:workspace_id>/', WorkspaceDetailView.as_view(), name='workspace-detail'),
]