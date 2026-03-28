"""
URL configuration for OIDC authentication.
"""
from django.urls import path
from .views import OIDCLoginView, OIDCCallbackView, OIDCLogoutView, CurrentUserView, AuthVerifyView

urlpatterns = [
    path('login/', OIDCLoginView.as_view(), name='oidc-login'),
    path('callback/', OIDCCallbackView.as_view(), name='oidc-callback'),
    path('logout/', OIDCLogoutView.as_view(), name='oidc-logout'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('verify/', AuthVerifyView.as_view(), name='auth-verify'),
]