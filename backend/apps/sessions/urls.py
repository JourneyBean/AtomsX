"""
URL configuration for Sessions API.
"""
from django.urls import path
from .views import (
    SessionStartView,
    SessionDetailView,
    SessionStreamView,
    SessionMessageView,
    SessionInterruptView,
    SessionResumeView,
)

urlpatterns = [
    # Session management
    path('', SessionStartView.as_view(), name='session-start'),  # POST with ?workspace_id=...
    path('<uuid:session_id>/', SessionDetailView.as_view(), name='session-detail'),
    path('<uuid:session_id>/stream/', SessionStreamView.as_view(), name='session-stream'),
    path('<uuid:session_id>/messages/', SessionMessageView.as_view(), name='session-messages'),
    path('<uuid:session_id>/interrupt/', SessionInterruptView.as_view(), name='session-interrupt'),
    path('<uuid:session_id>/resume/', SessionResumeView.as_view(), name='session-resume'),
]