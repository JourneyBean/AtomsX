"""
URL configuration for AtomsX Visual Coding Platform.
"""

from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Simple health check endpoint for container healthcheck and monitoring."""
    return JsonResponse({'status': 'healthy', 'service': 'atomsx-backend'})


urlpatterns = [
    path('api/health/', health_check, name='health_check'),
    path('api/auth/', include('apps.users.urls')),
    path('api/workspaces/', include('apps.workspaces.urls')),
    path('api/sessions/', include('apps.sessions.urls')),
]