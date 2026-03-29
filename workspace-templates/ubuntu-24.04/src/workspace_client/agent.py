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
from claude_agent_sdk.types import StreamEvent

from .config import settings

logger = logging.getLogger(__name__)


# Environment context for Claude Agent
# This informs Claude about the container environment and correct path usage
ENV_CONTEXT = """
## 环境信息

你正在 Docker 容器中运行，以下是你的运行环境：

### 工作目录
- **代码工作目录**: /home/user/workspace
- 所有文件操作（读取、写入、编辑）都应该使用相对于此目录的路径，或使用以此目录为根的绝对路径
- 示例：创建文件应使用 `/home/user/workspace/hello.py` 或 `hello.py`

### 用户数据
- **用户数据目录**: /home/user/data (如果存在)
- 这是用户持久化数据的存储位置

## 进程管理

容器使用 supervisord 管理多个进程。你可以使用 `supervisorctl` 命令：

- 查看进程状态: `supervisorctl status`
- 重启进程: `supervisorctl restart workspace-client` 或 `supervisorctl restart preview-server`
- 查看日志: `supervisorctl tail workspace-client`

## 实时预览

你可以启动一个开发服务器，用户将能够通过预览 URL 实时查看你的工作成果。

### 预览配置
- **预览端口**: 3000 (容器内部)
- **启动脚本**: /home/user/workspace/start_app.sh

### 如何启动预览

1. 创建 `start_app.sh` 脚本在 workspace 目录
2. 确保脚本可执行: `chmod +x start_app.sh`
3. 预览服务会自动启动

### 启动脚本示例

```bash
#!/bin/bash
npm run dev -- --port 3000 --host 0.0.0.0
```

### 常见框架启动命令

- **Vite**: `npm run dev -- --port 3000 --host 0.0.0.0`
- **Next.js**: `npm run dev -- -p 3000 -H 0.0.0.0`
- **Python HTTP**: `python3 -m http.server 3000 --bind 0.0.0.0`
- **Flask**: `flask run --host 0.0.0.0 --port 3000`
- **FastAPI**: `uvicorn main:app --host 0.0.0.0 --port 3000`

### 重要提示
- 必须监听 `0.0.0.0:3000`，不能只监听 localhost
- 如果 start_app.sh 不存在，将显示占位页面
- 用户可以通过预览 URL 立即查看你的工作成果

## 其他提示
- 不要使用 `/Users/...` 或其他宿主机路径
- 不要假设你在特定的开发环境中
- 当前工作目录是你的工作空间根目录
"""


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
    _history_context: Optional[str] = None  # Holds the conversation history for resume
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
            "permission_mode": "bypassPermissions",  # Allow all tool calls without user confirmation
            "include_partial_messages": True,  # Enable streaming output
            "system_prompt": {
                "type": "preset",
                "preset": "claude_code",
                "append": ENV_CONTEXT,
            },
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

        # Configure Claude SDK client options
        options_kwargs = {
            "cwd": Path("/home/user/workspace"),
            "env": env_vars,  # Always pass a dict, even if empty
            "permission_mode": "bypassPermissions",  # Allow all tool calls without user confirmation
            "include_partial_messages": True,  # Enable streaming output
            "system_prompt": {
                "type": "preset",
                "preset": "claude_code",
                "append": ENV_CONTEXT,
            },
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

        # Load and replay history messages to restore context
        history_messages = self.get_history_messages(history_session_id)
        if history_messages:
            logger.info(f"Replaying {len(history_messages)} history messages for context")
            # Build a context string from history
            context_parts = []
            for msg in history_messages:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                context_parts.append(f"{role}: {content}")

            # Store context for later use in send_message
            session._history_context = "\n\n".join(context_parts)
            logger.info(f"Stored history context ({len(session._history_context)} chars)")
        else:
            session._history_context = None

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
            # Build the message with history context if available
            full_message = message
            if hasattr(session, '_history_context') and session._history_context:
                # Prepend history context to the message
                full_message = f"""<conversation_history>
This is a continuation of a previous conversation. Here is the context:

{session._history_context}
</conversation_history>

<new_message>
{message}
</new_message>"""
                logger.info(f"Sending message with history context ({len(session._history_context)} chars)")

            # Send the query
            logger.info(f"Sending query to Claude SDK for session {session_id}...")
            await session.client.query(full_message)
            logger.info(f"Query sent, waiting for response...")

            full_response = ""
            current_tool = None

            # Stream responses - this runs in background task, not blocking WebSocket
            msg_count = 0
            async for msg in session.client.receive_response():
                msg_count += 1

                if session.is_interrupted:
                    logger.info(f"Session {session_id} was interrupted")
                    break

                # Handle StreamEvent for real-time streaming
                if isinstance(msg, StreamEvent):
                    event = msg.event
                    event_type = event.get("type")

                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            # Stream text in real-time
                            text = delta.get("text", "")
                            full_response += text
                            logger.info(f"[STREAM] Text delta received: {repr(text[:50])}...")
                            if stream_callback:
                                await stream_callback({
                                    "type": "stream",
                                    "session_id": session_id,
                                    "content": text,
                                })
                                logger.info(f"[STREAM] Callback completed for text delta")
                        elif delta.get("type") == "input_json_delta":
                            # Tool input streaming - just log for now
                            if current_tool:
                                chunk = delta.get("partial_json", "")
                                logger.debug(f"Tool {current_tool} input chunk: {chunk}")

                    elif event_type == "content_block_start":
                        content_block = event.get("content_block", {})
                        if content_block.get("type") == "tool_use":
                            current_tool = content_block.get("name")
                            tool_id = content_block.get("id", "")
                            logger.info(f"Tool call starting: {current_tool}")
                            if stream_callback:
                                await stream_callback({
                                    "type": "tool_use",
                                    "session_id": session_id,
                                    "tool_name": current_tool,
                                    "tool_input": {},  # Will be filled in later
                                })

                    elif event_type == "content_block_stop":
                        if current_tool:
                            logger.info(f"Tool call complete: {current_tool}")
                            current_tool = None

                # Handle complete AssistantMessage
                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            # Text already streamed via StreamEvent, just accumulate
                            pass
                        elif isinstance(block, ToolUseBlock):
                            if stream_callback:
                                await stream_callback({
                                    "type": "tool_use",
                                    "session_id": session_id,
                                    "tool_name": block.name,
                                    "tool_input": block.input,
                                })

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

    def get_history_list(self) -> list[dict]:
        """
        Get list of all history sessions.

        Returns:
            List of session metadata dicts, sorted by last_activity descending.
            Each dict contains:
            - history_session_id: str (folder name)
            - first_message: str (truncated to 50 chars)
            - last_activity: str (ISO timestamp)
        """
        sessions = []

        # Check if history directory exists
        if not self.history_dir.exists():
            logger.info("History directory does not exist")
            return sessions

        try:
            # List all subdirectories in history/
            for item in sorted(self.history_dir.iterdir(), key=lambda x: x.name, reverse=True):
                if not item.is_dir():
                    continue

                history_session_id = item.name

                # Read session.json for metadata
                session_file = item / "session.json"
                if not session_file.exists():
                    logger.warning(f"session.json not found in {history_session_id}")
                    continue

                try:
                    with open(session_file) as f:
                        session_data = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Failed to read session.json for {history_session_id}: {e}")
                    continue

                # Read first line of messages.jsonl for first user message
                first_message = ""
                messages_file = item / "messages.jsonl"
                if messages_file.exists():
                    try:
                        with open(messages_file) as f:
                            first_line = f.readline().strip()
                            if first_line:
                                msg_data = json.loads(first_line)
                                first_message = msg_data.get("user", "")[:50]
                    except (json.JSONDecodeError, IOError) as e:
                        logger.warning(f"Failed to read messages.jsonl for {history_session_id}: {e}")

                sessions.append({
                    "history_session_id": history_session_id,
                    "first_message": first_message,
                    "last_activity": session_data.get("last_activity", ""),
                })

            # Sort by last_activity descending
            sessions.sort(key=lambda x: x.get("last_activity", ""), reverse=True)

            logger.info(f"Found {len(sessions)} history sessions")
            return sessions

        except Exception as e:
            logger.error(f"Error listing history: {e}")
            return sessions

    def get_history_messages(self, history_session_id: str) -> list[dict]:
        """
        Get messages from a history session.

        Args:
            history_session_id: Folder name in history directory

        Returns:
            List of message dicts with role, content, timestamp
        """
        messages = []

        messages_file = self.history_dir / history_session_id / "messages.jsonl"

        if not messages_file.exists():
            logger.warning(f"Messages file not found for {history_session_id}")
            return messages

        try:
            with open(messages_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        msg_data = json.loads(line)
                        # Add user message
                        if msg_data.get("user"):
                            messages.append({
                                "role": "user",
                                "content": msg_data["user"],
                                "timestamp": msg_data.get("timestamp", ""),
                                "status": "complete",
                            })
                        # Add assistant message
                        if msg_data.get("assistant"):
                            messages.append({
                                "role": "agent",
                                "content": msg_data["assistant"],
                                "timestamp": msg_data.get("timestamp", ""),
                                "status": "complete",
                            })
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse message line: {e}")

            logger.info(f"Loaded {len(messages)} messages from {history_session_id}")
            return messages

        except Exception as e:
            logger.error(f"Error reading messages from {history_session_id}: {e}")
            return messages