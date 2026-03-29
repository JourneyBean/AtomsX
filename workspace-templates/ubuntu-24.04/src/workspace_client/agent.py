"""
Claude Agent SDK wrapper for Workspace Client.

Provides:
- SessionManager for multi-session support
- ActiveSession for running Claude conversations
- Session history persistence for resume

History Structure:
- /home/user/history/index.json - maps history_session_id -> session metadata
- /home/user/history/{history_session_id}/ - session folder
  - session.json - session metadata
  - messages.jsonl - conversation history (appending)
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, AsyncIterator
import httpx

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ToolUseBlock

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class ActiveSession:
    """
    Active Claude Agent session.

    Tracks:
    - Session ID for routing (from Backend)
    - History session ID (folder name in history directory)
    - Claude SDK client (async context manager)
    - Conversation history
    """

    session_id: str  # Backend routing session ID
    workspace_id: str
    history_session_id: Optional[str] = None  # Folder name in /home/user/history/
    client: Optional[ClaudeSDKClient] = None
    _client_context: Any = None  # Holds the async context manager
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = False
    is_interrupted: bool = False
    pending_user_input: bool = False


class SessionManager:
    """
    Manager for multiple concurrent Claude Agent sessions.

    Features:
    - Create new sessions
    - Resume existing sessions (via history replay)
    - Interrupt active sessions
    - Handle user input requests
    - Save and load session history
    """

    def __init__(self, workspace_id: str, history_dir: Path):
        """
        Initialize session manager.

        Args:
            workspace_id: UUID of the workspace
            history_dir: Directory for storing session history
        """
        self.workspace_id = workspace_id
        self.history_dir = history_dir
        self.sessions: dict[str, ActiveSession] = {}
        self._agent_config: Optional[dict] = None

        # Ensure history directory exists
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _generate_history_session_id(self) -> str:
        """
        Generate a short session ID for history folder.

        Uses timestamp + random suffix for uniqueness.
        Example: 20260328-1425-a3f2
        """
        import secrets
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M")
        suffix = secrets.token_hex(2)[:4]
        return f"{timestamp}-{suffix}"

    async def fetch_agent_config(self) -> dict:
        """
        Fetch agent configuration from backend internal API.

        Returns:
            Dict with anthropic_api_key and optional anthropic_base_url
        """
        if self._agent_config:
            return self._agent_config

        url = f"{settings.backend_http_url}/api/workspaces/internal/agent-config/{self.workspace_id}/"

        logger.info(f"Fetching agent config from: {url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"X-Internal-Token": settings.internal_api_token},
                    timeout=30.0,
                )
                response.raise_for_status()
                self._agent_config = response.json()
                logger.info("Agent config fetched successfully")
                return self._agent_config

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch agent config: HTTP {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch agent config: {e}")
            raise

    async def start_session(self, session_id: str) -> ActiveSession:
        """
        Start a new Claude Agent session.

        Args:
            session_id: UUID for the session (routing identifier from Backend)

        Returns:
            ActiveSession instance
        """
        # Check if session already exists
        if session_id in self.sessions:
            existing = self.sessions[session_id]
            if existing.is_active:
                logger.warning(f"Session {session_id} is already active")
                return existing

        # Get agent config (API key, base URL, etc.)
        config = await self.fetch_agent_config()

        # Generate history_session_id for this session
        history_session_id = self._generate_history_session_id()

        # Create session folder
        session_folder = self.history_dir / history_session_id
        session_folder.mkdir(parents=True, exist_ok=True)

        # Create session record
        session = ActiveSession(
            session_id=session_id,
            workspace_id=self.workspace_id,
            history_session_id=history_session_id,
        )

        # Build environment variables for Claude SDK
        env_vars = {}
        if config.get("anthropic_api_key"):
            env_vars["ANTHROPIC_API_KEY"] = config["anthropic_api_key"]
        if config.get("anthropic_base_url"):
            env_vars["ANTHROPIC_BASE_URL"] = config["anthropic_base_url"]

        logger.info(f"Claude SDK env config: {list(env_vars.keys())}")

        # Configure Claude SDK client options
        options_kwargs = {
            "cwd": Path("/home/user/workspace"),
            "env": env_vars,  # Always pass a dict, even if empty
        }

        # Add model if configured
        if config.get("anthropic_model"):
            options_kwargs["model"] = config["anthropic_model"]
            logger.info(f"Claude SDK model: {config['anthropic_model']}")

        options = ClaudeAgentOptions(**options_kwargs)

        # Create and enter Claude SDK client context
        session.client = ClaudeSDKClient(options=options)
        session._client_context = session.client.__aenter__()
        await session._client_context
        session.is_active = True

        self.sessions[session_id] = session

        # Save initial session metadata
        await self._save_session_history(session)

        logger.info(f"Started session {session_id} (history_session_id: {history_session_id})")

        return session

    async def resume_session(self, session_id: str, history_session_id: str) -> ActiveSession:
        """
        Resume an existing Claude Agent session.

        In the new SDK, resumption works by replaying conversation history
        through the message flow. We load our saved history for reference.

        Args:
            session_id: UUID for routing (from Backend)
            history_session_id: Folder name in /home/user/history/ to resume

        Returns:
            ActiveSession instance
        """
        # Check if already active
        if session_id in self.sessions:
            existing = self.sessions[session_id]
            if existing.is_active:
                logger.warning(f"Session {session_id} is already active")
                return existing

        # Load session metadata from history folder
        history_data = await self._load_session_history(history_session_id)

        # Get agent config (API key, base URL, etc.)
        config = await self.fetch_agent_config()

        # Create session record
        session = ActiveSession(
            session_id=session_id,
            workspace_id=self.workspace_id,
            history_session_id=history_session_id,
            created_at=datetime.fromisoformat(history_data.get("created_at", datetime.utcnow().isoformat())),
        )

        # Build environment variables for Claude SDK
        env_vars = {}
        if config.get("anthropic_api_key"):
            env_vars["ANTHROPIC_API_KEY"] = config["anthropic_api_key"]
        if config.get("anthropic_base_url"):
            env_vars["ANTHROPIC_BASE_URL"] = config["anthropic_base_url"]

        logger.info(f"Claude SDK env config: {list(env_vars.keys())}")

        # Configure Claude SDK client
        options = ClaudeAgentOptions(
            cwd=Path("/home/user/workspace"),
            env=env_vars,  # Always pass a dict, even if empty
        )

        # Create and enter Claude SDK client context
        session.client = ClaudeSDKClient(options=options)
        session._client_context = session.client.__aenter__()
        await session._client_context
        session.is_active = True

        self.sessions[session_id] = session

        logger.info(f"Resumed session {session_id} (history_session_id: {history_session_id})")

        return session

    async def interrupt_session(self, session_id: str) -> bool:
        """
        Interrupt an active session.

        Args:
            session_id: UUID of the session

        Returns:
            True if interrupted successfully
        """
        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found for interrupt")
            return False

        session = self.sessions[session_id]
        if not session.is_active:
            logger.warning(f"Session {session_id} is not active")
            return False

        # Mark as interrupted - the message loop will check this flag
        session.is_interrupted = True
        logger.info(f"Marked session {session_id} for interruption")

        return True

    async def send_message(
        self,
        session_id: str,
        message: str,
        stream_callback: Optional[callable] = None,
    ) -> Optional[str]:
        """
        Send a message to a session and collect responses.

        Args:
            session_id: UUID of the session
            message: User message text
            stream_callback: Callback for streaming responses

        Returns:
            Final response text or None if error
        """
        logger.info(f"send_message called for session {session_id}")

        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found")
            return None

        session = self.sessions[session_id]
        if not session.is_active or not session.client:
            logger.warning(f"Session {session_id} is not active")
            return None

        session.last_activity = datetime.utcnow()
        session.is_interrupted = False
        session.pending_user_input = False

        try:
            # Send the query
            logger.info(f"Sending query to Claude SDK for session {session_id}...")
            await session.client.query(message)
            logger.info(f"Query sent, waiting for response...")

            full_response = ""

            # Stream responses
            msg_count = 0
            async for msg in session.client.receive_response():
                msg_count += 1
                logger.info(f"Received message #{msg_count}: type={type(msg).__name__}")
                if session.is_interrupted:
                    logger.info(f"Session {session_id} was interrupted")
                    break

                # Handle different message types
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            full_response += block.text
                            if stream_callback:
                                await stream_callback({
                                    "type": "stream",
                                    "session_id": session_id,
                                    "content": block.text,
                                })
                        elif isinstance(block, ToolUseBlock):
                            if stream_callback:
                                await stream_callback({
                                    "type": "tool_use",
                                    "session_id": session_id,
                                    "tool_name": block.name,
                                    "tool_input": block.input,
                                })

                # Check for user input requests (result messages with ask permission)
                # The new SDK handles this through permission_mode and hooks
                # For now, we'll detect it from the message flow

            # Save message to history
            await self._save_message_history(session, message, full_response)

            if stream_callback:
                await stream_callback({
                    "type": "complete",
                    "session_id": session_id,
                })

            return full_response

        except Exception as e:
            logger.error(f"Error in session {session_id}: {e}")
            if stream_callback:
                await stream_callback({
                    "type": "error",
                    "session_id": session_id,
                    "error": str(e),
                })
            return None

    async def close_session(self, session_id: str):
        """
        Close and cleanup a session.

        Args:
            session_id: UUID of the session
        """
        if session_id not in self.sessions:
            return

        session = self.sessions[session_id]

        # Save final history
        await self._save_session_history(session)

        # Exit client context
        if session.client and session._client_context:
            try:
                await session.client.__aexit__(None, None, None)
            except Exception:
                pass

        session.is_active = False
        del self.sessions[session_id]

        logger.info(f"Closed session {session_id}")

    async def _save_session_history(self, session: ActiveSession):
        """
        Save session metadata to disk.

        Args:
            session: ActiveSession to save
        """
        if not session.history_session_id:
            return

        session_folder = self.history_dir / session.history_session_id
        session_folder.mkdir(parents=True, exist_ok=True)

        session_file = session_folder / "session.json"

        session_data = {
            "session_id": session.session_id,
            "history_session_id": session.history_session_id,
            "workspace_id": session.workspace_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
        }

        try:
            with open(session_file, "w") as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session history: {e}")

    async def _save_message_history(self, session: ActiveSession, user_message: str, response: str):
        """
        Save message exchange to history file.

        Args:
            session: ActiveSession
            user_message: User's message
            response: Claude's response
        """
        if not session.history_session_id:
            return

        messages_file = self.history_dir / session.history_session_id / "messages.jsonl"

        message_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user": user_message,
            "assistant": response,
        }

        try:
            with open(messages_file, "a") as f:
                f.write(json.dumps(message_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to save message history: {e}")

    async def _load_session_history(self, history_session_id: str) -> dict:
        """
        Load session history from disk.

        Args:
            history_session_id: Folder name in history directory

        Returns:
            History dict or empty dict if not found
        """
        session_file = self.history_dir / history_session_id / "session.json"

        if not session_file.exists():
            logger.warning(f"History session {history_session_id} not found")
            return {}

        try:
            with open(session_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load session history: {e}")
            return {}

    async def cleanup_all(self):
        """
        Cleanup all active sessions.
        """
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id)

        logger.info("All sessions cleaned up")