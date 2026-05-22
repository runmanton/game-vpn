"""
GameVPN - Signaling Server
==========================
Lightweight WebSocket server for peer discovery, room management, and key exchange.
Deploy free on Render/Railway/Fly.io or run locally.

Usage:
    pip install fastapi uvicorn websockets
    python signaling_server.py
"""

import asyncio
import json
import secrets
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import hub_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GameVPN-Server")

app = FastAPI(title="GameVPN Signaling Server", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class Peer:
    peer_id: str
    username: str
    public_key: str
    endpoint: str  # public IP:port from STUN
    local_ip: str  # assigned virtual LAN IP (10.10.x.x)
    websocket: Optional[WebSocket] = field(default=None, repr=False)
    last_seen: float = field(default_factory=time.time)
    nat_type: str = "unknown"  # full-cone, symmetric, etc.

    def to_dict(self):
        return {
            "peer_id": self.peer_id,
            "username": self.username,
            "public_key": self.public_key,
            "endpoint": self.endpoint,
            "local_ip": self.local_ip,
            "nat_type": self.nat_type,
        }


@dataclass
class Room:
    room_id: str
    room_code: str  # human-readable join code
    name: str
    host_id: str
    password: Optional[str] = None
    max_peers: int = 20
    created_at: float = field(default_factory=time.time)
    peers: dict[str, Peer] = field(default_factory=dict)
    subnet: str = "10.10.0.0/24"
    next_ip: int = 2  # start from 10.10.0.2

    def assign_ip(self) -> str:
        ip = f"10.10.0.{self.next_ip}"
        self.next_ip += 1
        return ip

    def to_dict(self):
        return {
            "room_id": self.room_id,
            "room_code": self.room_code,
            "name": self.name,
            "host_id": self.host_id,
            "max_peers": self.max_peers,
            "subnet": self.subnet,
            "peer_count": len(self.peers),
            "peers": {pid: p.to_dict() for pid, p in self.peers.items()},
        }


# ─── Server State ───────────────────────────────────────────────────────────────

rooms: dict[str, Room] = {}          # room_id -> Room
code_to_room: dict[str, str] = {}    # room_code -> room_id
peer_connections: dict[str, WebSocket] = {}  # peer_id -> WebSocket


def generate_room_code() -> str:
    """Generate a short, easy-to-share room code like 'ABCD-1234'."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, O to avoid confusion
    nums = "23456789"  # no 0, 1
    code = "".join(secrets.choice(chars) for _ in range(4)) + "-" + \
           "".join(secrets.choice(nums) for _ in range(4))
    return code


# ─── WebSocket Message Handlers ─────────────────────────────────────────────────

async def broadcast_to_room(room: Room, message: dict, exclude_peer: str = None):
    """Send message to all peers in room except excluded one."""
    for peer_id, peer in room.peers.items():
        if peer_id != exclude_peer and peer.websocket:
            try:
                await peer.websocket.send_json(message)
            except Exception:
                pass


async def handle_create_room(ws: WebSocket, data: dict) -> dict:
    """Create a new game room."""
    room_code = generate_room_code()
    while room_code in code_to_room:
        room_code = generate_room_code()

    room_id = secrets.token_hex(8)
    peer_id = data.get("peer_id", secrets.token_hex(8))

    room = Room(
        room_id=room_id,
        room_code=room_code,
        name=data.get("room_name", f"{data.get('username', 'Player')}'s Room"),
        host_id=peer_id,
        password=data.get("password"),
        max_peers=data.get("max_peers", 20),
    )

    # Host gets first IP
    local_ip = room.assign_ip()
    peer = Peer(
        peer_id=peer_id,
        username=data.get("username", "Host"),
        public_key=data.get("public_key", ""),
        endpoint=data.get("endpoint", ""),
        local_ip=local_ip,
        websocket=ws,
        nat_type=data.get("nat_type", "unknown"),
    )

    room.peers[peer_id] = peer
    rooms[room_id] = room
    code_to_room[room_code] = room_id
    peer_connections[peer_id] = ws

    logger.info(f"Room created: {room_code} by {peer.username} (peer={peer_id[:8]})")

    # Register the host's WireGuard key with the hub so the hub can route to it.
    if peer.public_key:
        await hub_client.add_peer(peer.public_key, local_ip)

    return {
        "type": "room_created",
        "room": room.to_dict(),
        "your_peer_id": peer_id,
        "your_local_ip": local_ip,
        "hub": await hub_client.fetch_info(),
    }


async def handle_join_room(ws: WebSocket, data: dict) -> dict:
    """Join an existing room by code."""
    room_code = data.get("room_code", "").upper().strip()

    if room_code not in code_to_room:
        return {"type": "error", "message": "Room not found. Check the code and try again."}

    room_id = code_to_room[room_code]
    room = rooms[room_id]

    # Check password
    if room.password and data.get("password") != room.password:
        return {"type": "error", "message": "Wrong password."}

    # Check capacity
    if len(room.peers) >= room.max_peers:
        return {"type": "error", "message": "Room is full."}

    peer_id = data.get("peer_id", secrets.token_hex(8))
    local_ip = room.assign_ip()

    peer = Peer(
        peer_id=peer_id,
        username=data.get("username", "Player"),
        public_key=data.get("public_key", ""),
        endpoint=data.get("endpoint", ""),
        local_ip=local_ip,
        websocket=ws,
        nat_type=data.get("nat_type", "unknown"),
    )

    room.peers[peer_id] = peer
    peer_connections[peer_id] = ws

    logger.info(f"Peer {peer.username} joined room {room_code} (peer={peer_id[:8]})")

    # Register the joiner's WireGuard key with the hub.
    if peer.public_key:
        await hub_client.add_peer(peer.public_key, local_ip)

    # Notify existing peers about the new joiner
    await broadcast_to_room(room, {
        "type": "peer_joined",
        "peer": peer.to_dict(),
    }, exclude_peer=peer_id)

    return {
        "type": "room_joined",
        "room": room.to_dict(),
        "your_peer_id": peer_id,
        "your_local_ip": local_ip,
        "hub": await hub_client.fetch_info(),
    }


async def handle_signal(ws: WebSocket, data: dict) -> Optional[dict]:
    """Relay WebRTC/connection signaling between peers (for NAT traversal)."""
    target_peer_id = data.get("target_peer_id")
    if target_peer_id in peer_connections:
        try:
            await peer_connections[target_peer_id].send_json({
                "type": "signal",
                "from_peer_id": data.get("from_peer_id"),
                "signal_data": data.get("signal_data"),
            })
        except Exception:
            return {"type": "error", "message": "Failed to reach target peer."}
    return None


async def handle_ping(ws: WebSocket, data: dict) -> dict:
    """Respond to keepalive pings."""
    peer_id = data.get("peer_id")
    if peer_id in peer_connections:
        # Update last_seen for any room this peer is in
        for room in rooms.values():
            if peer_id in room.peers:
                room.peers[peer_id].last_seen = time.time()
    return {"type": "pong", "timestamp": time.time()}


async def handle_leave_room(ws: WebSocket, data: dict) -> Optional[dict]:
    """Leave a room."""
    peer_id = data.get("peer_id")
    room_code = data.get("room_code", "").upper().strip()

    if room_code not in code_to_room:
        return None

    room_id = code_to_room[room_code]
    room = rooms[room_id]

    if peer_id in room.peers:
        leaving_peer = room.peers[peer_id]
        username = leaving_peer.username
        public_key = leaving_peer.public_key
        del room.peers[peer_id]

        if peer_id in peer_connections:
            del peer_connections[peer_id]

        logger.info(f"Peer {username} left room {room_code}")

        # Remove the WireGuard registration from the hub.
        if public_key:
            await hub_client.remove_peer(public_key)

        # Notify others
        await broadcast_to_room(room, {
            "type": "peer_left",
            "peer_id": peer_id,
            "username": username,
        })

        # If room is empty, clean up
        if not room.peers:
            del rooms[room_id]
            del code_to_room[room_code]
            logger.info(f"Room {room_code} deleted (empty)")

    return {"type": "left_room", "room_code": room_code}


async def handle_update_endpoint(ws: WebSocket, data: dict) -> Optional[dict]:
    """Update a peer's public endpoint after STUN discovery."""
    peer_id = data.get("peer_id")
    new_endpoint = data.get("endpoint", "")
    room_code = data.get("room_code", "").upper().strip()

    if room_code in code_to_room:
        room = rooms[code_to_room[room_code]]
        if peer_id in room.peers:
            room.peers[peer_id].endpoint = new_endpoint
            room.peers[peer_id].nat_type = data.get("nat_type", "unknown")

            # Notify other peers about endpoint update
            await broadcast_to_room(room, {
                "type": "peer_updated",
                "peer": room.peers[peer_id].to_dict(),
            }, exclude_peer=peer_id)

    return None


# ─── WebSocket Endpoint ─────────────────────────────────────────────────────────

MESSAGE_HANDLERS = {
    "create_room": handle_create_room,
    "join_room": handle_join_room,
    "signal": handle_signal,
    "ping": handle_ping,
    "leave_room": handle_leave_room,
    "update_endpoint": handle_update_endpoint,
}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_peer_id = None

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")
            handler = MESSAGE_HANDLERS.get(msg_type)

            if not handler:
                await ws.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})
                continue

            # Track which peer this connection belongs to
            if msg_type in ("create_room", "join_room"):
                connected_peer_id = data.get("peer_id")

            response = await handler(ws, data)
            if response:
                await ws.send_json(response)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected (peer={connected_peer_id})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up disconnected peer from all rooms
        if connected_peer_id:
            for room_code, room_id in list(code_to_room.items()):
                room = rooms.get(room_id)
                if room and connected_peer_id in room.peers:
                    leaving = room.peers[connected_peer_id]
                    username = leaving.username
                    public_key = leaving.public_key
                    del room.peers[connected_peer_id]
                    logger.info(f"Peer {username} disconnected from room {room_code}")

                    if public_key:
                        await hub_client.remove_peer(public_key)

                    await broadcast_to_room(room, {
                        "type": "peer_left",
                        "peer_id": connected_peer_id,
                        "username": username,
                    })

                    if not room.peers:
                        del rooms[room_id]
                        del code_to_room[room_code]
                        logger.info(f"Room {room_code} deleted (empty)")

            peer_connections.pop(connected_peer_id, None)


# ─── REST Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "GameVPN Signaling Server",
        "version": "1.1.0",
        "status": "running",
        "hub_enabled": hub_client.is_enabled(),
    }


@app.get("/rooms")
async def list_rooms():
    """List public rooms (without passwords)."""
    public_rooms = []
    for room in rooms.values():
        if not room.password:
            public_rooms.append({
                "room_code": room.room_code,
                "name": room.name,
                "peer_count": len(room.peers),
                "max_peers": room.max_peers,
            })
    return {"rooms": public_rooms}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "active_rooms": len(rooms),
        "connected_peers": len(peer_connections),
    }


# ─── Background Tasks ───────────────────────────────────────────────────────────

async def cleanup_stale_peers():
    """Remove peers that haven't pinged in 60 seconds."""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for room_code, room_id in list(code_to_room.items()):
            room = rooms.get(room_id)
            if not room:
                continue
            stale = [pid for pid, p in room.peers.items() if now - p.last_seen > 60]
            for pid in stale:
                stale_peer = room.peers[pid]
                username = stale_peer.username
                public_key = stale_peer.public_key
                del room.peers[pid]
                peer_connections.pop(pid, None)
                logger.info(f"Removed stale peer {username} from {room_code}")
                if public_key:
                    await hub_client.remove_peer(public_key)
                await broadcast_to_room(room, {
                    "type": "peer_left",
                    "peer_id": pid,
                    "username": username,
                })
            if not room.peers:
                del rooms[room_id]
                del code_to_room[room_code]
                logger.info(f"Room {room_code} deleted (all peers stale)")


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(cleanup_stale_peers())
    logger.info("GameVPN Signaling Server started!")


# ─── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
