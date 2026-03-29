"""
WebSocket client for Workspace Client.

Handles connection to backend with:
- Token authentication
- Automatic reconnection
- Message send/receive
- Ping/pong for keepalive
"""

import asyncio
import json
import logging
from typing import Callable, Optional
import websockets

from .config import settings

logger = logging.getLogger(__name__)


class WSClient:
    """
    WebSocket client for connecting to AtomsX backend.

    Features:
    - Token-based authentication via URL query parameter
    - Automatic reconnection with configurable delay
    - Ping/pong for connection keepalive
    - Async message handling with callbacks
    """

    def __init__(
        self,
        workspace_id: str,
        auth_token: str,
        on_message: Callable[[dict], None],
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize WebSocket client.

        Args:
            workspace_id: UUID of the workspace
            auth_token: Authentication token for the workspace
            on_message: Callback for received messages
            on_connect: Callback when connection established
            on_disconnect: Callback when connection lost
        """
        self.workspace_id = workspace_id
        self.auth_token = auth_token
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.should_reconnect = True
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    def _get_ws_url(self) -> str:
        """
        Get the WebSocket URL with authentication.

        URL format: ws://backend:8000/ws/workspace/{workspace_id}/?token={token}
        """
        base_url = settings.backend_ws_url
        return f"{base_url}/ws/workspace/{self.workspace_id}/?token={self.auth_token}"

    async def connect(self) -> bool:
        """
        Connect to the backend WebSocket.

        Returns:
            True if connection successful, False otherwise
        """
        ws_url = self._get_ws_url()
        logger.info(f"Connecting to WebSocket: {ws_url.split('?')[0]}...")

        try:
            self.ws = await websockets.connect(
                ws_url,
                ping_interval=settings.ping_interval,
                ping_timeout=10,
                close_timeout=5,
            )
            self.connected = True
            logger.info(f"WebSocket connected for workspace {self.workspace_id}")

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Start ping loop
            self._ping_task = asyncio.create_task(self._ping_loop())

            # Call on_connect callback
            if self.on_connect:
                self.on_connect()

            return True

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """
        Disconnect from the backend WebSocket.

        Stops reconnection attempts and closes the connection.
        """
        self.should_reconnect = False
        await self._close_connection()

    async def _close_connection(self):
        """Close the WebSocket connection and cleanup tasks."""
        self.connected = False

        # Cancel ping task
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        # Cancel receive task
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        # Close WebSocket
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

        # Call on_disconnect callback
        if self.on_disconnect:
            self.on_disconnect()

        logger.info(f"WebSocket disconnected for workspace {self.workspace_id}")

    async def send(self, message: dict) -> bool:
        """
        Send a message to the backend.

        Args:
            message: Message dict to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected or not self.ws:
            logger.warning("Cannot send: WebSocket not connected")
            return False

        try:
            await self.ws.send(json.dumps(message))
            logger.debug(f"Sent message: {message.get('type', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _receive_loop(self):
        """
        Continuous loop for receiving messages from backend.
        """
        try:
            while self.connected and self.ws:
                try:
                    raw_message = await self.ws.recv()
                    message = json.loads(raw_message)
                    logger.debug(f"Received message: {message.get('type', 'unknown')}")

                    # Handle pong response
                    if message.get('type') == 'pong':
                        continue

                    # Call message handler
                    await self.on_message(message)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("WebSocket connection closed by server")
                    self.connected = False
                    break
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    self.connected = False
                    break

        except asyncio.CancelledError:
            pass

        # Trigger disconnect callback and reconnection
        if self.connected:
            await self._close_connection()

        if self.should_reconnect:
            await self._reconnect()

    async def _ping_loop(self):
        """
        Periodic ping to keep connection alive and detect disconnects.
        """
        try:
            while self.connected:
                await asyncio.sleep(settings.ping_interval)
                if self.connected and self.ws:
                    try:
                        await self.send({'type': 'ping'})
                    except Exception:
                        logger.warning("Ping failed, connection may be lost")
                        self.connected = False
                        break
        except asyncio.CancelledError:
            pass

    async def _reconnect(self):
        """
        Attempt to reconnect after disconnect.

        Uses exponential backoff with max delay.
        """
        delay = settings.reconnect_delay
        max_delay = 60.0

        while self.should_reconnect and not self.connected:
            logger.info(f"Attempting reconnect in {delay}s...")
            await asyncio.sleep(delay)

            if not self.should_reconnect:
                break

            success = await self.connect()
            if success:
                logger.info("Reconnected successfully")
                break

            # Exponential backoff
            delay = min(delay * 2, max_delay)

    async def run(self):
        """
        Main run loop - connects and maintains connection.
        """
        await self.connect()

        # Keep running while connected or reconnecting
        while self.connected or (self.should_reconnect and self._receive_task):
            await asyncio.sleep(1)