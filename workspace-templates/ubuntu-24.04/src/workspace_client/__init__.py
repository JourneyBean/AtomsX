"""
Workspace Client for AtomsX.

A Python client that runs inside workspace containers and:
- Connects to backend via WebSocket
- Executes tasks using Claude Agent SDK
- Supports multi-session parallel execution
- Handles session resume, interrupt, and user input
"""

from .config import settings, Settings
from .client import WSClient
from .agent import SessionManager, ActiveSession
from .main import WorkspaceClient, run

__all__ = [
    "settings",
    "Settings",
    "WSClient",
    "SessionManager",
    "ActiveSession",
    "WorkspaceClient",
    "run",
]