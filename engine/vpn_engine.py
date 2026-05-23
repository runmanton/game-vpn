"""
GameVPN - Network Engine
========================
Manages WireGuard tunnels, STUN NAT traversal, and relay fallback.
Creates a virtual LAN interface so games see all peers as local network.
"""

import subprocess
import os
import sys
import json
import socket
import struct
import time
import logging
import secrets
import tempfile
import ipaddress
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("GameVPN-Engine")

# On Windows, subprocess.run() flashes a console window by default when the
# parent process has no console (PyInstaller --windowed). CREATE_NO_WINDOW
# keeps these helper invocations silent.
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _find_wg_tool() -> str:
    """Locate the `wg` binary. Falls back to PATH if not in a known location."""
    if sys.platform == "win32":
        for p in (
            r"C:\Program Files\WireGuard\wg.exe",
            r"C:\Program Files (x86)\WireGuard\wg.exe",
        ):
            if os.path.exists(p):
                return p
    return "wg"


WG_TOOL = _find_wg_tool()


# ─── WireGuard Key Management ──────────────────────────────────────────────────

@dataclass
class WireGuardKeys:
    private_key: str = ""
    public_key: str = ""

    @staticmethod
    def generate() -> "WireGuardKeys":
        """Generate a WireGuard keypair using the wg command."""
        try:
            private = subprocess.check_output(
                [WG_TOOL, "genkey"], text=True, creationflags=NO_WINDOW
            ).strip()
            public = subprocess.check_output(
                [WG_TOOL, "pubkey"], input=private, text=True, creationflags=NO_WINDOW
            ).strip()
            return WireGuardKeys(private_key=private, public_key=public)
        except FileNotFoundError:
            # No real wg available. The previous behavior silently generated
            # random base64 blobs as a "fallback" -- that's catastrophic on
            # the production path because the private key no longer
            # corresponds to the public key, so handshakes with the hub fail
            # silently. Raise instead so the GUI can surface a clear error.
            raise RuntimeError(
                "WireGuard CLI (wg.exe) not found. Install WireGuard from "
                "https://www.wireguard.com/install/ and reopen GameVPN."
            )


# ─── STUN Client (NAT Traversal) ───────────────────────────────────────────────

STUN_SERVERS = [
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun2.l.google.com", 19302),
    ("stun.stunprotocol.org", 3478),
]


@dataclass
class STUNResult:
    public_ip: str = ""
    public_port: int = 0
    nat_type: str = "unknown"
    local_ip: str = ""
    local_port: int = 0


def stun_discover(local_port: int = 0) -> STUNResult:
    """
    Perform STUN binding request to discover public IP/port and NAT type.
    Uses Google's free STUN servers.
    """
    result = STUNResult()

    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        result.local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        result.local_ip = "127.0.0.1"

    # STUN Binding Request (RFC 5389)
    # Message Type: 0x0001 (Binding Request)
    # Magic Cookie: 0x2112A442
    # Transaction ID: 12 random bytes
    transaction_id = secrets.token_bytes(12)
    magic_cookie = 0x2112A442

    stun_request = struct.pack(
        "!HHI12s",
        0x0001,  # Message Type: Binding Request
        0x0000,  # Message Length: 0 (no attributes)
        magic_cookie,
        transaction_id,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    if local_port:
        sock.bind(("0.0.0.0", local_port))
    else:
        sock.bind(("0.0.0.0", 0))

    result.local_port = sock.getsockname()[1]

    for stun_host, stun_port in STUN_SERVERS:
        try:
            sock.sendto(stun_request, (stun_host, stun_port))
            data, addr = sock.recvfrom(1024)

            if len(data) < 20:
                continue

            # Parse STUN response
            msg_type, msg_len, cookie = struct.unpack("!HHI", data[:8])
            resp_tid = data[8:20]

            if msg_type != 0x0101:  # Not Binding Success Response
                continue
            if resp_tid != transaction_id:
                continue

            # Parse attributes
            offset = 20
            while offset < 20 + msg_len:
                if offset + 4 > len(data):
                    break
                attr_type, attr_len = struct.unpack("!HH", data[offset : offset + 4])
                attr_data = data[offset + 4 : offset + 4 + attr_len]

                # XOR-MAPPED-ADDRESS (0x0020) or MAPPED-ADDRESS (0x0001)
                if attr_type in (0x0020, 0x0001):
                    family = attr_data[1]
                    if family == 0x01:  # IPv4
                        if attr_type == 0x0020:
                            # XOR with magic cookie
                            port = struct.unpack("!H", attr_data[2:4])[0] ^ (magic_cookie >> 16)
                            ip_bytes = struct.unpack("!I", attr_data[4:8])[0] ^ magic_cookie
                        else:
                            port = struct.unpack("!H", attr_data[2:4])[0]
                            ip_bytes = struct.unpack("!I", attr_data[4:8])[0]

                        ip = socket.inet_ntoa(struct.pack("!I", ip_bytes))
                        result.public_ip = ip
                        result.public_port = port

                # Pad to 4-byte boundary
                offset += 4 + attr_len + (4 - attr_len % 4) % 4

            if result.public_ip:
                # Determine NAT type (simplified)
                if result.public_ip == result.local_ip:
                    result.nat_type = "no-nat"
                elif result.public_port == result.local_port:
                    result.nat_type = "full-cone"
                else:
                    result.nat_type = "symmetric"
                break

        except socket.timeout:
            continue
        except Exception as e:
            logger.debug(f"STUN error with {stun_host}: {e}")
            continue

    sock.close()
    return result


# ─── WireGuard Interface Manager ───────────────────────────────────────────────

class WireGuardManager:
    """Manages WireGuard tunnel interface on Windows.

    Hub-and-spoke topology: the only [Peer] entry written to the local
    tunnel config is the GameVPN relay hub. All virtual-LAN traffic
    (10.10.0.0/24) is routed through the hub, which forwards between
    peers. This bypasses NAT problems (symmetric, CGNAT) that would
    otherwise break direct P2P.
    """

    def __init__(self, interface_name: str = "GameVPN"):
        self.interface_name = interface_name
        self.config_dir = Path(tempfile.gettempdir()) / "gamevpn"
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / f"{interface_name}.conf"
        self.keys = WireGuardKeys.generate()
        self.is_running = False
        self.peers: dict[str, dict] = {}
        self.hub_public_key: str = ""
        self.hub_endpoint: str = ""

    def set_hub(self, public_key: str, endpoint: str):
        self.hub_public_key = public_key
        self.hub_endpoint = endpoint

    def _find_wireguard(self) -> Optional[str]:
        """Find WireGuard installation path on Windows."""
        possible_paths = [
            r"C:\Program Files\WireGuard\wireguard.exe",
            r"C:\Program Files (x86)\WireGuard\wireguard.exe",
        ]
        for p in possible_paths:
            if os.path.exists(p):
                return p

        # Try PATH
        try:
            result = subprocess.run(
                ["where", "wireguard"], capture_output=True, text=True,
                creationflags=NO_WINDOW,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return None

    def generate_config(self, local_ip: str, listen_port: int = 51820) -> str:
        """Generate WireGuard configuration file content (hub-and-spoke).

        The only Peer is the relay hub. AllowedIPs = 10.10.0.0/24 means
        every packet destined for the virtual LAN goes to the hub, which
        forwards it to the correct peer.
        """
        if not self.hub_public_key or not self.hub_endpoint:
            raise RuntimeError(
                "Hub info not set. Call set_hub() before starting the tunnel."
            )
        return (
            "[Interface]\n"
            f"PrivateKey = {self.keys.private_key}\n"
            f"Address = {local_ip}/24\n"
            f"ListenPort = {listen_port}\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {self.hub_public_key}\n"
            f"Endpoint = {self.hub_endpoint}\n"
            "AllowedIPs = 10.10.0.0/24\n"
            "PersistentKeepalive = 25\n"
        )

    def write_config(self, local_ip: str, listen_port: int = 51820):
        """Write WireGuard config to file."""
        config = self.generate_config(local_ip, listen_port)
        self.config_path.write_text(config)
        logger.info(f"WireGuard config written to {self.config_path}")
        return self.config_path

    def add_peer(self, peer_id: str, public_key: str, endpoint: str, local_ip: str):
        """Track a peer locally for UI / ping purposes.

        In hub-and-spoke mode the tunnel config is NOT touched -- routing for
        all 10.10.0.x addresses already goes via the hub. This dict is kept so
        the GUI can list peers and the ping timer can probe them.
        """
        self.peers[peer_id] = {
            "public_key": public_key,
            "endpoint": endpoint,
            "local_ip": local_ip,
        }
        logger.info(f"Tracking peer {peer_id[:8]} ({local_ip}) - routed via hub")

    def remove_peer(self, peer_id: str):
        """Untrack a peer locally."""
        if peer_id in self.peers:
            del self.peers[peer_id]
            logger.info(f"Untracking peer {peer_id[:8]}")

    def start_tunnel(self, local_ip: str, listen_port: int = 51820) -> bool:
        """Start WireGuard tunnel."""
        wg_path = self._find_wireguard()
        if not wg_path:
            logger.error("WireGuard not installed! Please install from https://www.wireguard.com/install/")
            return False

        self.write_config(local_ip, listen_port)

        try:
            # Install and start the tunnel service
            subprocess.run(
                [wg_path, "/installtunnelservice", str(self.config_path)],
                check=True, capture_output=True, text=True,
                creationflags=NO_WINDOW,
            )
            self.is_running = True
            logger.info(f"WireGuard tunnel '{self.interface_name}' started on {local_ip}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start WireGuard: {e.stderr}")
            return False

    def stop_tunnel(self) -> bool:
        """Stop WireGuard tunnel."""
        wg_path = self._find_wireguard()
        if not wg_path:
            return False

        try:
            subprocess.run(
                [wg_path, "/uninstalltunnelservice", self.interface_name],
                check=True, capture_output=True, text=True,
                creationflags=NO_WINDOW,
            )
            self.is_running = False
            logger.info(f"WireGuard tunnel '{self.interface_name}' stopped")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop WireGuard: {e.stderr}")
            return False

    def reload_config(self, local_ip: str, listen_port: int = 51820) -> bool:
        """Reload WireGuard config.

        In hub-and-spoke mode there is nothing to reload when peers join/leave
        -- the hub config is static (just the hub) and the hub itself handles
        peer routing. Kept as a no-op to preserve the API surface.
        """
        return True

    def get_status(self) -> dict:
        """Get WireGuard tunnel status."""
        try:
            result = subprocess.run(
                [WG_TOOL, "show", self.interface_name],
                capture_output=True, text=True,
                creationflags=NO_WINDOW,
            )
            if result.returncode == 0:
                return {"running": True, "output": result.stdout}
        except Exception:
            pass
        return {"running": self.is_running, "output": ""}


# ─── VPN Engine (main orchestrator) ─────────────────────────────────────────────

class VPNEngine:
    """
    Main VPN engine that coordinates:
    - STUN NAT traversal
    - WireGuard tunnel management
    - Peer connection management
    """

    def __init__(self):
        self.wg = WireGuardManager()
        self.stun_result: Optional[STUNResult] = None
        self.local_ip: str = ""
        self.listen_port: int = 51820
        self.connected: bool = False

    def set_hub(self, public_key: str, endpoint: str):
        """Configure the relay hub the tunnel should attach to."""
        self.wg.set_hub(public_key, endpoint)

    def discover_nat(self) -> STUNResult:
        """Run STUN discovery to find public endpoint."""
        logger.info("Running STUN NAT discovery...")
        self.stun_result = stun_discover(self.listen_port)
        logger.info(
            f"STUN result: {self.stun_result.public_ip}:{self.stun_result.public_port} "
            f"(NAT type: {self.stun_result.nat_type})"
        )
        return self.stun_result

    def get_public_key(self) -> str:
        return self.wg.keys.public_key

    def get_endpoint(self) -> str:
        if self.stun_result:
            return f"{self.stun_result.public_ip}:{self.stun_result.public_port}"
        return ""

    def get_nat_type(self) -> str:
        if self.stun_result:
            return self.stun_result.nat_type
        return "unknown"

    def setup_tunnel(self, local_ip: str) -> bool:
        """Initialize and start the VPN tunnel."""
        self.local_ip = local_ip
        return self.wg.start_tunnel(local_ip, self.listen_port)

    def add_peer(self, peer_id: str, public_key: str, endpoint: str, local_ip: str):
        """Add a peer and reload tunnel config."""
        self.wg.add_peer(peer_id, public_key, endpoint, local_ip)
        if self.wg.is_running:
            self.wg.reload_config(self.local_ip, self.listen_port)

    def remove_peer(self, peer_id: str):
        """Remove a peer and reload tunnel config."""
        self.wg.remove_peer(peer_id)
        if self.wg.is_running:
            self.wg.reload_config(self.local_ip, self.listen_port)

    def start(self, local_ip: str) -> bool:
        """Full startup sequence."""
        self.local_ip = local_ip
        self.discover_nat()
        success = self.setup_tunnel(local_ip)
        self.connected = success
        return success

    def stop(self):
        """Shut down VPN."""
        self.wg.stop_tunnel()
        self.connected = False
        # Clean up temp config
        try:
            if self.wg.config_path.exists():
                self.wg.config_path.unlink()
        except Exception:
            pass

    def ping_peer(self, peer_ip: str, timeout: float = 2.0) -> Optional[float]:
        """Ping a peer and return latency in ms, or None if unreachable."""
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", str(int(timeout * 1000)), peer_ip],
                    capture_output=True, text=True, timeout=timeout + 1,
                    creationflags=NO_WINDOW,
                )
            else:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", str(int(timeout)), peer_ip],
                    capture_output=True, text=True, timeout=timeout + 1,
                )

            if result.returncode == 0:
                # Parse ping time
                output = result.stdout
                if "time=" in output:
                    time_str = output.split("time=")[1].split()[0].rstrip("ms")
                    return float(time_str)
                elif "time<" in output:
                    return 0.5  # < 1ms
        except Exception:
            pass
        return None


# ─── Relay Engine (fallback when P2P fails) ─────────────────────────────────────

class RelayEngine:
    """
    Simple UDP relay for when direct P2P connection fails.
    Uses the signaling server as a relay point.
    This is the fallback mechanism for symmetric NAT situations.
    """

    def __init__(self, relay_host: str, relay_port: int = 8766):
        self.relay_host = relay_host
        self.relay_port = relay_port
        self.sock: Optional[socket.socket] = None
        self.active = False

    def start(self):
        """Start relay connection."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5)
        self.active = True
        logger.info(f"Relay engine started, target: {self.relay_host}:{self.relay_port}")

    def stop(self):
        """Stop relay."""
        self.active = False
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, data: bytes, target_peer_id: str):
        """Send data through relay."""
        if self.sock and self.active:
            # Prefix with target peer ID
            header = target_peer_id.encode().ljust(16, b"\x00")
            self.sock.sendto(header + data, (self.relay_host, self.relay_port))

    def receive(self, buffer_size: int = 65535) -> Optional[tuple[bytes, str]]:
        """Receive data from relay. Returns (data, from_peer_id)."""
        if self.sock and self.active:
            try:
                data, addr = self.sock.recvfrom(buffer_size)
                from_peer_id = data[:16].rstrip(b"\x00").decode()
                return data[16:], from_peer_id
            except socket.timeout:
                return None
        return None
