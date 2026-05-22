"""
GameVPN - WebSocket Client
==========================
Handles communication with the signaling server.
"""

import asyncio
import json
import logging
import secrets
import time
from typing import Optional, Callable

import websockets

logger = logging.getLogger("GameVPN-Client")


class SignalingClient:
    """WebSocket client for communicating with the signaling server."""

    def __init__(self, server_url: str = "ws://localhost:8765/ws"):
        self.server_url = server_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.peer_id: str = secrets.token_hex(8)
        self.connected: bool = False
        self.room_code: str = ""
        self.room_info: dict = {}
        self._on_message: Optional[Callable] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None

    def set_message_handler(self, handler: Callable):
        """Set callback for incoming messages."""
        self._on_message = handler

    async def connect(self) -> bool:
        """Connect to the signaling server."""
        try:
            self.ws = await websockets.connect(
                self.server_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self.connected = True
            logger.info(f"Connected to signaling server: {self.server_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to signaling server: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from the signaling server."""
        if self._ping_task:
            self._ping_task.cancel()
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.connected = False
        logger.info("Disconnected from signaling server")

    async def send(self, message: dict):
        """Send a message to the server."""
        if self.ws and self.connected:
            try:
                await self.ws.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                self.connected = False

    async def create_room(
        self,
        username: str,
        room_name: str,
        public_key: str,
        endpoint: str,
        nat_type: str = "unknown",
        password: str = None,
        max_peers: int = 20,
    ) -> dict:
        """Create a new game room."""
        msg = {
            "type": "create_room",
            "peer_id": self.peer_id,
            "username": username,
            "room_name": room_name,
            "public_key": public_key,
            "endpoint": endpoint,
            "nat_type": nat_type,
            "max_peers": max_peers,
        }
        if password:
            msg["password"] = password

        await self.send(msg)

        # Wait for response
        response = await self._receive_one()
        if response and response.get("type") == "room_created":
            self.room_code = response["room"]["room_code"]
            self.room_info = response["room"]
            self.peer_id = response.get("your_peer_id", self.peer_id)
        return response or {}

    async def join_room(
        self,
        room_code: str,
        username: str,
        public_key: str,
        endpoint: str,
        nat_type: str = "unknown",
        password: str = None,
    ) -> dict:
        """Join an existing room by code."""
        msg = {
            "type": "join_room",
            "peer_id": self.peer_id,
            "room_code": room_code,
            "username": username,
            "public_key": public_key,
            "endpoint": endpoint,
            "nat_type": nat_type,
        }
        if password:
            msg["password"] = password

        await self.send(msg)

        response = await self._receive_one()
        if response and response.get("type") == "room_joined":
            self.room_code = room_code
            self.room_info = response["room"]
            self.peer_id = response.get("your_peer_id", self.peer_id)
        return response or {}

    async def leave_room(self):
        """Leave the current room."""
        if self.room_code:
            await self.send({
                "type": "leave_room",
                "peer_id": self.peer_id,
                "room_code": self.room_code,
            })
            self.room_code = ""
            self.room_info = {}

    async def update_endpoint(self, endpoint: str, nat_type: str = "unknown"):
        """Update our public endpoint."""
        if self.room_code:
            await self.send({
                "type": "update_endpoint",
                "peer_id": self.peer_id,
                "room_code": self.room_code,
                "endpoint": endpoint,
                "nat_type": nat_type,
            })

    async def send_signal(self, target_peer_id: str, signal_data: dict):
        """Send signaling data to a specific peer (for NAT traversal)."""
        await self.send({
            "type": "signal",
            "from_peer_id": self.peer_id,
            "target_peer_id": target_peer_id,
            "signal_data": signal_data,
        })

    async def _receive_one(self, timeout: float = 10.0) -> Optional[dict]:
        """Receive a single message with timeout."""
        if not self.ws:
            return None
        try:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            return json.loads(raw)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for server response")
            return None
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None

    async def start_listening(self):
        """Start listening for incoming messages in the background."""
        self._listen_task = asyncio.create_task(self._listen_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _listen_loop(self):
        """Background loop to listen for incoming messages."""
        while self.connected and self.ws:
            try:
                raw = await self.ws.recv()
                data = json.loads(raw)
                if self._on_message:
                    self._on_message(data)
            except websockets.ConnectionClosed:
                logger.info("WebSocket connection closed")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Listen error: {e}")
                await asyncio.sleep(1)

    async def _ping_loop(self):
        """Send periodic pings to keep connection alive."""
        while self.connected:
            try:
                await asyncio.sleep(15)
                if self.connected:
                    await self.send({
                        "type": "ping",
                        "peer_id": self.peer_id,
                    })
            except asyncio.CancelledError:
                break
            except Exception:
                pass
