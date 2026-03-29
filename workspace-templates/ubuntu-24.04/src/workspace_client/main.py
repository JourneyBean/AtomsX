"""
Main entrypoint for Workspace Client.

Handles:
- WebSocket connection to backend
- Message routing to SessionManager
- Task execution with Claude Agent SDK
- SSE stream forwarding to backend
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

from .config import settings
from .client import WSClient
from .agent import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/home/user/workspace-client.log"),
    ],
)
logger = logging.getLogger(__name__)


class WorkspaceClient:
    """
    Main Workspace Client class.

    Orchestrates:
    - WebSocket connection to backend
    - Session management with Claude Agent
    - Message handling and routing
    """

    def __init__(self):
        """Initialize Workspace Client."""
        self.workspace_id = settings.workspace_id
        self.auth_token = settings.auth_token
        self.history_dir = Path(settings.history_dir)

        # Initialize session manager
        self.session_manager = SessionManager(self.workspace_id, self.history_dir)

        # Initialize WebSocket client
        self.ws_client = WSClient(
            workspace_id=self.workspace_id,
            auth_token=self.auth_token,
            on_message=self._handle_message,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

        self.running = False
        self._shutdown_event = asyncio.Event()
        # Track background tasks
        self._background_tasks: dict[str, asyncio.Task] = {}

    async def start(self):
        """
        Start the Workspace Client.

        Connects to backend WebSocket and starts message handling loop.
        """
        logger.info(f"Starting Workspace Client for workspace {self.workspace_id}")
        self.running = True

        try:
            # Start WebSocket connection
            await self.ws_client.run()

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"Workspace Client error: {e}")
            raise

        finally:
            await self.shutdown()

    async def shutdown(self):
        """
        Shutdown Workspace Client gracefully.

        Closes all sessions and disconnects from backend.
        """
        logger.info("Shutting down Workspace Client")
        self.running = False

        # Cancel all background tasks
        for task_id, task in self._background_tasks.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled background task: {task_id}")

        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks.values(), return_exceptions=True)

        # Cleanup sessions
        await self.session_manager.cleanup_all()

        # Disconnect WebSocket
        await self.ws_client.disconnect()

        self._shutdown_event.set()

    def _on_connect(self):
        """Callback when WebSocket connects."""
        logger.info("Connected to backend WebSocket")

    def _on_disconnect(self):
        """Callback when WebSocket disconnects."""
        logger.warning("Disconnected from backend WebSocket")

    async def _handle_message(self, message: dict):
        """
        Handle incoming message from backend.

        Message types:
        - task: Start a new task/session
        - resume: Resume existing session
        - interrupt: Interrupt active session
        - user_input: User response for ask_user
        - ping: Ping message (handled by client)

        Args:
            message: Message dict from backend
        """
        message_type = message.get("type")

        logger.info(f"Received message: {message_type}")

        try:
            if message_type == "task":
                # Run task in background to not block other messages
                await self._handle_task(message)

            elif message_type == "resume":
                # Run resume in background to not block other messages
                await self._handle_resume(message)

            elif message_type == "interrupt":
                await self._handle_interrupt(message)

            elif message_type == "user_input":
                await self._handle_user_input(message)

            elif message_type == "get_history":
                await self._handle_get_history(message)

            elif message_type == "get_history_messages":
                await self._handle_get_history_messages(message)

            elif message_type == "ping":
                # Ping handled by client, just respond with pong
                await self.ws_client.send({"type": "pong"})

            elif message_type == "connected":
                # Connection confirmation from backend
                logger.info("Received connection confirmation from backend")

            else:
                logger.warning(f"Unknown message type: {message_type}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_error(message.get("session_id"), str(e))

    async def _handle_task(self, message: dict):
        """
        Handle task message - start a new session.

        Args:
            message: Task message with session_id and prompt
        """
        session_id = message.get("session_id")
        prompt = message.get("prompt")

        logger.info(f"Handling task: session_id={session_id}, prompt={prompt[:50] if prompt else 'None'}...")

        if not session_id or not prompt:
            logger.error(f"Missing session_id or prompt: session_id={session_id}, prompt={prompt}")
            await self._send_error(session_id, "Missing session_id or prompt")
            return

        # Start session (quick operation)
        try:
            session = await self.session_manager.start_session(session_id)
            logger.info(f"Session {session_id} started successfully")
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            await self._send_error(session_id, str(e))
            return

        # Send acknowledgment
        await self.ws_client.send({
            "type": "started",
            "session_id": session_id,
            "history_session_id": session.history_session_id,
        })

        # Execute task in background to not block WebSocket
        task = asyncio.create_task(
            self._execute_session_task(session_id, prompt)
        )
        self._background_tasks[session_id] = task
        task.add_done_callback(lambda t: self._background_tasks.pop(session_id, None))

    async def _execute_session_task(self, session_id: str, prompt: str):
        """
        Execute session task in background.

        This runs independently so WebSocket can handle other messages.
        """
        try:
            logger.info(f"Executing task with prompt: {prompt[:100]}...")
            session = self.session_manager.sessions.get(session_id)

            response = await self.session_manager.send_message(
                session_id,
                prompt,
                stream_callback=self._send_stream_event,
            )
            logger.info(f"Task completed, response length: {len(response) if response else 0}")

            # Send completion if not waiting for user input
            if session and not session.pending_user_input:
                await self.ws_client.send({
                    "type": "complete",
                    "session_id": session_id,
                    "response": response,
                })

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            await self._send_error(session_id, str(e))

    async def _handle_resume(self, message: dict):
        """
        Handle resume message - resume existing session from history.

        Args:
            message: Resume message with session_id and history_session_id
        """
        session_id = message.get("session_id")
        history_session_id = message.get("history_session_id")  # Folder name in history
        prompt = message.get("prompt")

        if not session_id or not history_session_id or not prompt:
            await self._send_error(
                session_id,
                "Missing session_id, history_session_id, or prompt",
            )
            return

        # Resume session (quick operation)
        try:
            session = await self.session_manager.resume_session(
                session_id,
                history_session_id,
            )
        except Exception as e:
            logger.error(f"Failed to resume session: {e}")
            await self._send_error(session_id, str(e))
            return

        # Send acknowledgment
        await self.ws_client.send({
            "type": "resumed",
            "session_id": session_id,
            "history_session_id": history_session_id,
        })

        # Execute task in background to not block WebSocket
        task = asyncio.create_task(
            self._execute_resume_task(session_id, prompt)
        )
        self._background_tasks[session_id] = task
        task.add_done_callback(lambda t: self._background_tasks.pop(session_id, None))

    async def _execute_resume_task(self, session_id: str, prompt: str):
        """
        Execute resumed session task in background.

        This runs independently so WebSocket can handle other messages.
        """
        try:
            session = self.session_manager.sessions.get(session_id)

            response = await self.session_manager.send_message(
                session_id,
                prompt,
                stream_callback=self._send_stream_event,
            )

            # Send completion if not waiting for user input
            if session and not session.pending_user_input:
                await self.ws_client.send({
                    "type": "complete",
                    "session_id": session_id,
                    "response": response,
                })

        except Exception as e:
            logger.error(f"Resume execution error: {e}")
            await self._send_error(session_id, str(e))

    async def _handle_interrupt(self, message: dict):
        """
        Handle interrupt message - interrupt active session.

        Args:
            message: Interrupt message with session_id
        """
        session_id = message.get("session_id")

        if not session_id:
            await self._send_error(None, "Missing session_id")
            return

        try:
            success = await self.session_manager.interrupt_session(session_id)

            await self.ws_client.send({
                "type": "interrupted",
                "session_id": session_id,
                "success": success,
            })

        except Exception as e:
            logger.error(f"Interrupt error: {e}")
            await self._send_error(session_id, str(e))

    async def _handle_user_input(self, message: dict):
        """
        Handle user_input message - respond to ask_user question.

        Args:
            message: User input message with session_id and response
        """
        session_id = message.get("session_id")
        user_response = message.get("response")

        if not session_id or not user_response:
            await self._send_error(session_id, "Missing session_id or response")
            return

        try:
            # Continue session with user input
            response = await self.session_manager.handle_user_input(
                session_id,
                user_response,
                stream_callback=self._send_stream_event,
            )

            # Send completion
            session = self.session_manager.sessions.get(session_id)
            if session and not session.pending_user_input:
                await self.ws_client.send({
                    "type": "complete",
                    "session_id": session_id,
                    "response": response,
                })

        except Exception as e:
            logger.error(f"User input handling error: {e}")
            await self._send_error(session_id, str(e))

    async def _handle_get_history(self, message: dict):
        """
        Handle get_history message - return list of history sessions.

        Args:
            message: Get history message with optional request_id
        """
        request_id = message.get("request_id")

        try:
            # Get history list from session manager
            sessions = self.session_manager.get_history_list()

            # Send response
            response = {
                "type": "history_list",
                "sessions": sessions,
            }
            if request_id:
                response["request_id"] = request_id

            await self.ws_client.send(response)
            logger.info(f"Sent history list with {len(sessions)} sessions")

        except Exception as e:
            logger.error(f"Get history error: {e}")
            error_response = {
                "type": "error",
                "error": str(e),
            }
            if request_id:
                error_response["request_id"] = request_id
            await self.ws_client.send(error_response)

    async def _handle_get_history_messages(self, message: dict):
        """
        Handle get_history_messages message - return messages from a history session.

        Args:
            message: Get history messages message with history_session_id and request_id
        """
        request_id = message.get("request_id")
        history_session_id = message.get("history_session_id")

        if not history_session_id:
            error_response = {
                "type": "error",
                "error": "Missing history_session_id",
            }
            if request_id:
                error_response["request_id"] = request_id
            await self.ws_client.send(error_response)
            return

        try:
            # Get messages from session manager
            messages = self.session_manager.get_history_messages(history_session_id)

            # Send response
            response = {
                "type": "history_messages",
                "history_session_id": history_session_id,
                "messages": messages,
            }
            if request_id:
                response["request_id"] = request_id

            await self.ws_client.send(response)
            logger.info(f"Sent {len(messages)} messages for history {history_session_id}")

        except Exception as e:
            logger.error(f"Get history messages error: {e}")
            error_response = {
                "type": "error",
                "error": str(e),
            }
            if request_id:
                error_response["request_id"] = request_id
            await self.ws_client.send(error_response)

    async def _send_stream_event(self, event: dict):
        """
        Send stream event to backend via WebSocket.

        Args:
            event: Stream event dict
        """
        logger.info(f"Sending stream event: type={event.get('type')}, session_id={event.get('session_id')}")
        await self.ws_client.send(event)

    async def _send_error(self, session_id: str, error: str):
        """
        Send error message to backend.

        Args:
            session_id: Session UUID (optional)
            error: Error message
        """
        await self.ws_client.send({
            "type": "error",
            "session_id": session_id,
            "error": error,
        })


async def main():
    """
    Main async entrypoint.
    """
    client = WorkspaceClient()

    # Setup signal handlers
    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        client._shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    finally:
        await client.shutdown()


def run():
    """
    Synchronous entrypoint for script execution.
    """
    asyncio.run(main())


if __name__ == "__main__":
    run()