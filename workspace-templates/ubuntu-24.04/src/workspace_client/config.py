"""
Configuration for Workspace Client.

Loads environment variables for:
- Authentication token (ATOMSX_AUTH_TOKEN)
- Backend WebSocket URL (ATOMSX_BACKEND_WS_URL)
- Backend HTTP URL (ATOMSX_BACKEND_HTTP_URL)
- Workspace ID (WORKSPACE_ID)
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Workspace Client settings loaded from environment."""

    # Authentication
    auth_token: str = Field(
        ...,
        alias="ATOMSX_AUTH_TOKEN",
        description="Token for WebSocket authentication",
    )

    # Backend URLs
    backend_ws_url: str = Field(
        default="ws://backend:8000",
        alias="ATOMSX_BACKEND_WS_URL",
        description="WebSocket URL for backend connection",
    )
    backend_http_url: str = Field(
        default="http://backend:8000",
        alias="ATOMSX_BACKEND_HTTP_URL",
        description="HTTP URL for backend API",
    )

    # Workspace info
    workspace_id: str = Field(
        ...,
        alias="WORKSPACE_ID",
        description="UUID of this workspace",
    )

    # Internal API token for fetching agent config
    internal_api_token: str = Field(
        default="dev-internal-token",
        alias="ATOMSX_INTERNAL_API_TOKEN",
        description="Token for internal API authentication",
    )

    # History storage
    history_dir: str = Field(
        default="/home/user/history",
        description="Directory for session history storage",
    )

    # Connection settings
    reconnect_delay: float = Field(
        default=5.0,
        description="Delay before reconnecting after disconnect",
    )
    ping_interval: float = Field(
        default=30.0,
        description="Interval for sending ping messages",
    )

    model_config = {
        "env_file": None,  # Only use environment variables
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()