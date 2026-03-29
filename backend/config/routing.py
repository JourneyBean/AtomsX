"""
WebSocket URL routing for AtomsX Visual Coding Platform.
"""

from django.urls import re_path
from apps.workspaces.consumers import WorkspaceConsumer

# WebSocket URL patterns
websocket_urlpatterns = [
    # Workspace WebSocket endpoint
    re_path(r'ws/workspace/(?P<workspace_id>[\w-]+)/$', WorkspaceConsumer.as_asgi()),
]