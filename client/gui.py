"""
GameVPN - Desktop GUI
=====================
PyQt6-based Windows desktop application for GameVPN.
Features: Create/Join rooms, peer list, ping monitor, connection status.
"""

import sys
import asyncio
import logging
import threading
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox, QFrame,
    QStackedWidget, QListWidget, QListWidgetItem, QMessageBox,
    QSpinBox, QCheckBox, QStatusBar, QSplitter, QProgressBar,
    QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QPalette, QPixmap, QAction

logger = logging.getLogger("GameVPN-GUI")

# Production signaling server (hardcoded so end users do not need to type it).
DEFAULT_SERVER_URL = "wss://gamevpn-tuan.onrender.com/ws"

# ─── Styles ─────────────────────────────────────────────────────────────────────

DARK_STYLE = """
QMainWindow {
    background-color: #1a1a2e;
}
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    margin-top: 12px;
    padding: 15px;
    padding-top: 25px;
    background-color: #16213e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 15px;
    padding: 0 8px;
    color: #00d4ff;
    font-weight: bold;
    font-size: 14px;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #1a5276;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #1a5276;
    border-color: #00d4ff;
}
QPushButton:pressed {
    background-color: #00d4ff;
    color: #1a1a2e;
}
QPushButton:disabled {
    background-color: #2a2a4a;
    color: #666;
    border-color: #333;
}
QPushButton#primaryBtn {
    background-color: #00d4ff;
    color: #1a1a2e;
    font-size: 15px;
    padding: 12px 30px;
}
QPushButton#primaryBtn:hover {
    background-color: #00bcd4;
}
QPushButton#dangerBtn {
    background-color: #e74c3c;
    border-color: #c0392b;
}
QPushButton#dangerBtn:hover {
    background-color: #c0392b;
}
QLineEdit {
    background-color: #0a1628;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 10px 15px;
    color: #e0e0e0;
    font-size: 14px;
    selection-background-color: #00d4ff;
}
QLineEdit:focus {
    border-color: #00d4ff;
}
QLineEdit#roomCode {
    font-size: 24px;
    font-weight: bold;
    text-align: center;
    letter-spacing: 4px;
    color: #00d4ff;
}
QTextEdit {
    background-color: #0a1628;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 10px;
    color: #b0b0b0;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}
QListWidget {
    background-color: #0a1628;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 5px;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 6px;
    margin: 2px;
}
QListWidget::item:selected {
    background-color: #0f3460;
}
QListWidget::item:hover {
    background-color: #16213e;
}
QStatusBar {
    background-color: #0a1628;
    color: #00d4ff;
    border-top: 1px solid #2a2a4a;
    font-size: 12px;
}
QSpinBox {
    background-color: #0a1628;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    padding: 8px;
    color: #e0e0e0;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #2a2a4a;
    background-color: #0a1628;
}
QCheckBox::indicator:checked {
    background-color: #00d4ff;
    border-color: #00d4ff;
}
QProgressBar {
    border: 1px solid #2a2a4a;
    border-radius: 5px;
    text-align: center;
    background-color: #0a1628;
    color: #e0e0e0;
    height: 8px;
}
QProgressBar::chunk {
    background-color: #00d4ff;
    border-radius: 4px;
}
QLabel#headerLabel {
    font-size: 28px;
    font-weight: bold;
    color: #00d4ff;
}
QLabel#subLabel {
    font-size: 13px;
    color: #8899aa;
}
QLabel#statusConnected {
    color: #2ecc71;
    font-weight: bold;
}
QLabel#statusDisconnected {
    color: #e74c3c;
    font-weight: bold;
}
QFrame#separator {
    background-color: #2a2a4a;
    max-height: 1px;
}
"""


# ─── Async Worker Thread ────────────────────────────────────────────────────────

class AsyncWorker(QThread):
    """Runs asyncio event loop in a separate thread for non-blocking network ops."""

    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks = []

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_coroutine(self, coro):
        """Schedule a coroutine on the async loop."""
        if self.loop and self.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future
        return None

    def stop(self):
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait()


# ─── Main Window ────────────────────────────────────────────────────────────────

class GameVPNApp(QMainWindow):
    """Main application window."""

    # Signals for thread-safe UI updates
    log_signal = pyqtSignal(str)
    peer_update_signal = pyqtSignal(dict)
    status_signal = pyqtSignal(str)
    room_created_signal = pyqtSignal(dict)
    room_joined_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    peer_joined_signal = pyqtSignal(dict)
    peer_left_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameVPN - Virtual LAN for Gaming")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)

        # State
        self.username = ""
        self.room_code = ""
        self.local_ip = ""
        self.peers: dict = {}
        self.is_connected = False
        self.vpn_engine = None
        self.signaling_client = None

        # Async worker
        self.async_worker = AsyncWorker()
        self.async_worker.start()

        # Connect signals
        self.log_signal.connect(self._append_log)
        self.peer_update_signal.connect(self._update_peer_list)
        self.room_created_signal.connect(self._on_room_created)
        self.room_joined_signal.connect(self._on_room_joined)
        self.error_signal.connect(self._on_error)
        self.peer_joined_signal.connect(self._on_peer_joined)
        self.peer_left_signal.connect(self._on_peer_left)

        # Build UI
        self._build_ui()

        # Ping timer
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self._ping_peers)
        self.ping_timer.setInterval(5000)

    def _build_ui(self):
        """Build the main UI."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 15, 20, 10)
        main_layout.setSpacing(15)

        # ── Header ──
        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        title = QLabel("🎮  GameVPN")
        title.setObjectName("headerLabel")
        title_layout.addWidget(title)
        subtitle = QLabel("Virtual LAN — Play together from anywhere")
        subtitle.setObjectName("subLabel")
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Connection status indicator
        self.status_indicator = QLabel("● Disconnected")
        self.status_indicator.setObjectName("statusDisconnected")
        self.status_indicator.setFont(QFont("Segoe UI", 12))
        header_layout.addWidget(self.status_indicator)

        main_layout.addLayout(header_layout)

        # ── Stacked Pages ──
        self.pages = QStackedWidget()
        main_layout.addWidget(self.pages)

        # Page 0: Home (Create/Join)
        self.pages.addWidget(self._build_home_page())

        # Page 1: Room View (connected)
        self.pages.addWidget(self._build_room_page())

        # ── Status Bar ──
        self.statusBar().showMessage("Ready — Enter your name and create or join a room")

    def _build_home_page(self) -> QWidget:
        """Build the home/lobby page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # Server URL is hardcoded so end users don't need to type it.
        # Kept as a widget (not added to layout) so existing read sites still work.
        self.server_input = QLineEdit(DEFAULT_SERVER_URL)

        # ── Player Info ──
        player_group = QGroupBox("Player Info")
        player_layout = QHBoxLayout(player_group)

        player_layout.addWidget(QLabel("Your Name:"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your game name...")
        self.username_input.setMaxLength(20)
        player_layout.addWidget(self.username_input, stretch=1)

        layout.addWidget(player_group)

        # ── Action Buttons ──
        actions_layout = QHBoxLayout()

        # Create Room
        create_group = QGroupBox("Create New Room")
        create_layout = QVBoxLayout(create_group)

        self.room_name_input = QLineEdit()
        self.room_name_input.setPlaceholderText("Room name (optional)")
        create_layout.addWidget(self.room_name_input)

        room_options_layout = QHBoxLayout()
        room_options_layout.addWidget(QLabel("Max players:"))
        self.max_peers_spin = QSpinBox()
        self.max_peers_spin.setRange(2, 20)
        self.max_peers_spin.setValue(10)
        room_options_layout.addWidget(self.max_peers_spin)
        room_options_layout.addStretch()

        self.password_check = QCheckBox("Password protected")
        room_options_layout.addWidget(self.password_check)
        create_layout.addLayout(room_options_layout)

        self.room_password_input = QLineEdit()
        self.room_password_input.setPlaceholderText("Room password")
        self.room_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.room_password_input.setVisible(False)
        self.password_check.toggled.connect(self.room_password_input.setVisible)
        create_layout.addWidget(self.room_password_input)

        self.create_btn = QPushButton("🚀  Create Room")
        self.create_btn.setObjectName("primaryBtn")
        self.create_btn.clicked.connect(self._on_create_room)
        create_layout.addWidget(self.create_btn)
        actions_layout.addWidget(create_group)

        # Join Room
        join_group = QGroupBox("Join Existing Room")
        join_layout = QVBoxLayout(join_group)

        join_layout.addWidget(QLabel("Enter Room Code:"))
        self.join_code_input = QLineEdit()
        self.join_code_input.setObjectName("roomCode")
        self.join_code_input.setPlaceholderText("ABCD-1234")
        self.join_code_input.setMaxLength(9)
        self.join_code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        join_layout.addWidget(self.join_code_input)

        self.join_password_input = QLineEdit()
        self.join_password_input.setPlaceholderText("Password (if required)")
        self.join_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        join_layout.addWidget(self.join_password_input)

        self.join_btn = QPushButton("🔗  Join Room")
        self.join_btn.setObjectName("primaryBtn")
        self.join_btn.clicked.connect(self._on_join_room)
        join_layout.addWidget(self.join_btn)

        join_layout.addStretch()
        actions_layout.addWidget(join_group)

        layout.addLayout(actions_layout)

        # ── Log Area ──
        log_group = QGroupBox("Connection Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        return page

    def _build_room_page(self) -> QWidget:
        """Build the in-room page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # ── Room Info Header ──
        room_header = QHBoxLayout()

        room_info_layout = QVBoxLayout()
        self.room_title_label = QLabel("Room: ")
        self.room_title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.room_title_label.setStyleSheet("color: #00d4ff;")
        room_info_layout.addWidget(self.room_title_label)

        code_layout = QHBoxLayout()
        code_label = QLabel("Room Code:")
        code_label.setStyleSheet("color: #8899aa;")
        code_layout.addWidget(code_label)
        self.room_code_label = QLabel("")
        self.room_code_label.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
        self.room_code_label.setStyleSheet("color: #2ecc71; letter-spacing: 3px;")
        self.room_code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_layout.addWidget(self.room_code_label)

        self.copy_code_btn = QPushButton("📋 Copy")
        self.copy_code_btn.setMinimumWidth(110)
        self.copy_code_btn.clicked.connect(self._copy_room_code)
        code_layout.addWidget(self.copy_code_btn)
        code_layout.addStretch()
        room_info_layout.addLayout(code_layout)

        room_header.addLayout(room_info_layout)
        room_header.addStretch()

        # Network info
        net_info_layout = QVBoxLayout()
        self.your_ip_label = QLabel("Your LAN IP: —")
        self.your_ip_label.setStyleSheet("color: #f39c12; font-weight: bold;")
        net_info_layout.addWidget(self.your_ip_label)
        self.nat_label = QLabel("NAT Type: —")
        self.nat_label.setStyleSheet("color: #8899aa;")
        net_info_layout.addWidget(self.nat_label)
        room_header.addLayout(net_info_layout)

        layout.addLayout(room_header)

        # ── Main Content Split ──
        content_layout = QHBoxLayout()

        # Left: Peer List
        peers_group = QGroupBox("Connected Peers")
        peers_layout = QVBoxLayout(peers_group)
        self.peer_list = QListWidget()
        self.peer_list.setMinimumWidth(300)
        peers_layout.addWidget(self.peer_list)

        self.peer_count_label = QLabel("0 peers connected")
        self.peer_count_label.setStyleSheet("color: #8899aa; font-size: 11px;")
        peers_layout.addWidget(self.peer_count_label)
        content_layout.addWidget(peers_group, stretch=1)

        # Right: Log & Controls
        right_layout = QVBoxLayout()

        # Network Log
        netlog_group = QGroupBox("Network Log")
        netlog_layout = QVBoxLayout(netlog_group)
        self.room_log_text = QTextEdit()
        self.room_log_text.setReadOnly(True)
        netlog_layout.addWidget(self.room_log_text)
        right_layout.addWidget(netlog_group, stretch=1)

        # Controls
        controls_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 Refresh Peers")
        self.refresh_btn.clicked.connect(self._refresh_peers)
        controls_layout.addWidget(self.refresh_btn)

        controls_layout.addStretch()

        self.disconnect_btn = QPushButton("⛔ Disconnect")
        self.disconnect_btn.setObjectName("dangerBtn")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        controls_layout.addWidget(self.disconnect_btn)

        right_layout.addLayout(controls_layout)
        content_layout.addLayout(right_layout, stretch=1)

        layout.addLayout(content_layout)

        return page

    # ─── Actions ────────────────────────────────────────────────────────────────

    def _on_create_room(self):
        """Handle Create Room button click."""
        username = self.username_input.text().strip()
        if not username:
            QMessageBox.warning(self, "Missing Info", "Please enter your name!")
            return

        self.username = username
        server_url = self.server_input.text().strip()
        room_name = self.room_name_input.text().strip() or f"{username}'s Room"
        password = self.room_password_input.text() if self.password_check.isChecked() else None
        max_peers = self.max_peers_spin.value()

        self.create_btn.setEnabled(False)
        self.join_btn.setEnabled(False)
        self.log_signal.emit("Discovering NAT type...")
        self.statusBar().showMessage("Connecting...")

        # Run async operations
        self.async_worker.run_coroutine(
            self._async_create_room(server_url, username, room_name, password, max_peers)
        )

    async def _async_create_room(self, server_url, username, room_name, password, max_peers):
        """Async create room operation."""
        try:
            # Import engine
            sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
            from engine.vpn_engine import VPNEngine

            self.vpn_engine = VPNEngine()

            # STUN discovery
            self.log_signal.emit("Running STUN NAT discovery...")
            stun_result = self.vpn_engine.discover_nat()
            endpoint = self.vpn_engine.get_endpoint()
            public_key = self.vpn_engine.get_public_key()
            nat_type = self.vpn_engine.get_nat_type()

            self.log_signal.emit(f"Public endpoint: {endpoint} (NAT: {nat_type})")

            # Connect to signaling server
            from client.vpn_client import SignalingClient
            self.signaling_client = SignalingClient(server_url)
            self.signaling_client.set_message_handler(self._handle_server_message)

            self.log_signal.emit("Connecting to signaling server...")
            connected = await self.signaling_client.connect()
            if not connected:
                self.error_signal.emit("Failed to connect to signaling server!")
                return

            # Create room
            self.log_signal.emit("Creating room...")
            response = await self.signaling_client.create_room(
                username=username,
                room_name=room_name,
                public_key=public_key,
                endpoint=endpoint,
                nat_type=nat_type,
                password=password,
                max_peers=max_peers,
            )

            if response.get("type") == "room_created":
                self.room_created_signal.emit(response)
                await self.signaling_client.start_listening()
            else:
                self.error_signal.emit(response.get("message", "Failed to create room"))

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")

    def _on_join_room(self):
        """Handle Join Room button click."""
        username = self.username_input.text().strip()
        room_code = self.join_code_input.text().strip().upper()

        if not username:
            QMessageBox.warning(self, "Missing Info", "Please enter your name!")
            return
        if not room_code:
            QMessageBox.warning(self, "Missing Info", "Please enter the room code!")
            return

        self.username = username
        server_url = self.server_input.text().strip()
        password = self.join_password_input.text() or None

        self.create_btn.setEnabled(False)
        self.join_btn.setEnabled(False)
        self.log_signal.emit(f"Joining room {room_code}...")
        self.statusBar().showMessage("Connecting...")

        self.async_worker.run_coroutine(
            self._async_join_room(server_url, room_code, username, password)
        )

    async def _async_join_room(self, server_url, room_code, username, password):
        """Async join room operation."""
        try:
            sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
            from engine.vpn_engine import VPNEngine

            self.vpn_engine = VPNEngine()

            # STUN discovery
            self.log_signal.emit("Running STUN NAT discovery...")
            self.vpn_engine.discover_nat()
            endpoint = self.vpn_engine.get_endpoint()
            public_key = self.vpn_engine.get_public_key()
            nat_type = self.vpn_engine.get_nat_type()

            self.log_signal.emit(f"Public endpoint: {endpoint} (NAT: {nat_type})")

            # Connect to signaling server
            from client.vpn_client import SignalingClient
            self.signaling_client = SignalingClient(server_url)
            self.signaling_client.set_message_handler(self._handle_server_message)

            self.log_signal.emit("Connecting to signaling server...")
            connected = await self.signaling_client.connect()
            if not connected:
                self.error_signal.emit("Failed to connect to signaling server!")
                return

            # Join room
            response = await self.signaling_client.join_room(
                room_code=room_code,
                username=username,
                public_key=public_key,
                endpoint=endpoint,
                nat_type=nat_type,
                password=password,
            )

            if response.get("type") == "room_joined":
                self.room_joined_signal.emit(response)
                await self.signaling_client.start_listening()
            else:
                self.error_signal.emit(response.get("message", "Failed to join room"))

        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}")

    def _on_disconnect(self):
        """Handle disconnect button click."""
        reply = QMessageBox.question(
            self, "Disconnect",
            "Are you sure you want to disconnect from the room?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._disconnect()

    def _disconnect(self):
        """Disconnect from room and VPN."""
        if self.signaling_client:
            self.async_worker.run_coroutine(self.signaling_client.leave_room())
            self.async_worker.run_coroutine(self.signaling_client.disconnect())

        if self.vpn_engine:
            self.vpn_engine.stop()

        self.ping_timer.stop()
        self.is_connected = False
        self.peers = {}
        self.room_code = ""

        self.peer_list.clear()
        self.room_log_text.clear()

        self.status_indicator.setText("● Disconnected")
        self.status_indicator.setObjectName("statusDisconnected")
        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)

        self.create_btn.setEnabled(True)
        self.join_btn.setEnabled(True)

        self.pages.setCurrentIndex(0)
        self.statusBar().showMessage("Disconnected")
        self.log_signal.emit("Disconnected from room")

    # ─── Server Message Handler ─────────────────────────────────────────────────

    def _handle_server_message(self, data: dict):
        """Handle incoming messages from the signaling server (called from async thread)."""
        msg_type = data.get("type", "")

        if msg_type == "peer_joined":
            self.peer_joined_signal.emit(data)
        elif msg_type == "peer_left":
            self.peer_left_signal.emit(data)
        elif msg_type == "peer_updated":
            self.peer_update_signal.emit(data.get("peer", {}))
        elif msg_type == "signal":
            # Handle NAT traversal signaling
            self.log_signal.emit(f"Signal from peer {data.get('from_peer_id', '')[:8]}")
        elif msg_type == "pong":
            pass  # Keepalive response
        else:
            self.log_signal.emit(f"Server: {msg_type}")

    # ─── UI Update Slots ────────────────────────────────────────────────────────

    def _configure_hub(self, hub_info):
        """Pass relay hub info into the VPN engine before the tunnel starts."""
        if not self.vpn_engine:
            return
        if not hub_info or not hub_info.get("public_key") or not hub_info.get("endpoint"):
            self.log_signal.emit(
                "WARNING: signaling server did not return relay hub info; "
                "VPN tunnel will not be reachable."
            )
            return
        self.vpn_engine.set_hub(hub_info["public_key"], hub_info["endpoint"])
        self.log_signal.emit(f"Relay hub: {hub_info['endpoint']}")

    def _on_room_created(self, response: dict):
        """Room successfully created."""
        room = response.get("room", {})
        self.room_code = room.get("room_code", "")
        self.local_ip = response.get("your_local_ip", "")
        self._configure_hub(response.get("hub"))

        self.room_title_label.setText(f"🎮  {room.get('name', 'Game Room')}")
        self.room_code_label.setText(self.room_code)
        self.your_ip_label.setText(f"Your LAN IP: {self.local_ip}")
        self.nat_label.setText(f"NAT Type: {self.vpn_engine.get_nat_type() if self.vpn_engine else '—'}")

        self._room_log(f"Room created! Share code: {self.room_code}")
        self._room_log(f"Your virtual LAN IP: {self.local_ip}")
        self._room_log("Waiting for players to join...")

        # Update peers
        for pid, pinfo in room.get("peers", {}).items():
            self.peers[pid] = pinfo

        self._refresh_peer_list_ui()
        self.is_connected = True
        self.status_indicator.setText("● Connected")
        self.status_indicator.setObjectName("statusConnected")
        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)

        self.pages.setCurrentIndex(1)
        self.statusBar().showMessage(f"Room: {self.room_code} — Share this code with friends!")
        self.ping_timer.start()

        # Start WireGuard tunnel
        if self.vpn_engine:
            self.log_signal.emit("Starting VPN tunnel...")
            success = self.vpn_engine.start(self.local_ip)
            if success:
                self._room_log("VPN tunnel active!")
            else:
                self._room_log("⚠ VPN tunnel failed — WireGuard may not be installed")
                self._room_log("Install WireGuard from: https://www.wireguard.com/install/")

    def _on_room_joined(self, response: dict):
        """Successfully joined a room."""
        room = response.get("room", {})
        self.room_code = room.get("room_code", "")
        self.local_ip = response.get("your_local_ip", "")
        self._configure_hub(response.get("hub"))

        self.room_title_label.setText(f"🎮  {room.get('name', 'Game Room')}")
        self.room_code_label.setText(self.room_code)
        self.your_ip_label.setText(f"Your LAN IP: {self.local_ip}")
        self.nat_label.setText(f"NAT Type: {self.vpn_engine.get_nat_type() if self.vpn_engine else '—'}")

        self._room_log(f"Joined room: {self.room_code}")
        self._room_log(f"Your virtual LAN IP: {self.local_ip}")

        # Load existing peers
        for pid, pinfo in room.get("peers", {}).items():
            self.peers[pid] = pinfo
            self._room_log(f"  ├ {pinfo.get('username', '?')} — {pinfo.get('local_ip', '?')}")

            # Add to WireGuard
            if self.vpn_engine and pid != self.signaling_client.peer_id:
                self.vpn_engine.add_peer(
                    pid, pinfo.get("public_key", ""),
                    pinfo.get("endpoint", ""), pinfo.get("local_ip", ""),
                )

        self._refresh_peer_list_ui()
        self.is_connected = True
        self.status_indicator.setText("● Connected")
        self.status_indicator.setObjectName("statusConnected")
        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)

        self.pages.setCurrentIndex(1)
        self.statusBar().showMessage(f"Connected to room: {self.room_code}")
        self.ping_timer.start()

        # Start WireGuard tunnel
        if self.vpn_engine:
            success = self.vpn_engine.start(self.local_ip)
            if success:
                self._room_log("VPN tunnel active!")
            else:
                self._room_log("⚠ VPN tunnel failed — WireGuard may not be installed")
                self._room_log("Install WireGuard from: https://www.wireguard.com/install/")

    def _on_peer_joined(self, data: dict):
        """A new peer joined the room."""
        peer = data.get("peer", {})
        peer_id = peer.get("peer_id", "")
        username = peer.get("username", "?")

        self.peers[peer_id] = peer
        self._room_log(f"✅ {username} joined! (IP: {peer.get('local_ip', '?')})")
        self._refresh_peer_list_ui()

        # Add to WireGuard
        if self.vpn_engine:
            self.vpn_engine.add_peer(
                peer_id, peer.get("public_key", ""),
                peer.get("endpoint", ""), peer.get("local_ip", ""),
            )

    def _on_peer_left(self, data: dict):
        """A peer left the room."""
        peer_id = data.get("peer_id", "")
        username = data.get("username", "?")

        if peer_id in self.peers:
            del self.peers[peer_id]

        self._room_log(f"❌ {username} disconnected")
        self._refresh_peer_list_ui()

        # Remove from WireGuard
        if self.vpn_engine:
            self.vpn_engine.remove_peer(peer_id)

    def _on_error(self, message: str):
        """Handle error messages."""
        self.log_signal.emit(f"ERROR: {message}")
        self.create_btn.setEnabled(True)
        self.join_btn.setEnabled(True)
        self.statusBar().showMessage(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)

    def _update_peer_list(self, peer_data: dict):
        """Update a peer's info in the list."""
        peer_id = peer_data.get("peer_id", "")
        if peer_id in self.peers:
            self.peers[peer_id].update(peer_data)
            self._refresh_peer_list_ui()

    def _refresh_peer_list_ui(self):
        """Refresh the peer list widget."""
        self.peer_list.clear()
        for pid, pinfo in self.peers.items():
            username = pinfo.get("username", "Unknown")
            local_ip = pinfo.get("local_ip", "?.?.?.?")
            nat_type = pinfo.get("nat_type", "?")
            is_self = self.signaling_client and pid == self.signaling_client.peer_id

            text = f"{'⭐ ' if is_self else '👤 '}{username}    IP: {local_ip}    NAT: {nat_type}"
            if is_self:
                text += "  (You)"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, pid)

            if is_self:
                item.setForeground(QColor("#00d4ff"))
            else:
                item.setForeground(QColor("#e0e0e0"))

            self.peer_list.addItem(item)

        count = len(self.peers)
        self.peer_count_label.setText(f"{count} peer{'s' if count != 1 else ''} connected")

    def _copy_room_code(self):
        """Copy room code to clipboard."""
        if self.room_code:
            QApplication.clipboard().setText(self.room_code)
            self.statusBar().showMessage("Room code copied to clipboard!", 3000)

    def _refresh_peers(self):
        """Refresh peer list."""
        self._refresh_peer_list_ui()
        self._room_log("Peer list refreshed")

    def _ping_peers(self):
        """Ping all peers to check latency."""
        if not self.vpn_engine or not self.is_connected:
            return

        for pid, pinfo in self.peers.items():
            if self.signaling_client and pid == self.signaling_client.peer_id:
                continue
            local_ip = pinfo.get("local_ip", "")
            if local_ip:
                latency = self.vpn_engine.ping_peer(local_ip, timeout=1.0)
                if latency is not None:
                    self._update_peer_ping(pid, latency)

    def _update_peer_ping(self, peer_id: str, latency: float):
        """Update ping display for a peer."""
        for i in range(self.peer_list.count()):
            item = self.peer_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == peer_id:
                pinfo = self.peers.get(peer_id, {})
                username = pinfo.get("username", "?")
                local_ip = pinfo.get("local_ip", "?")
                text = f"👤 {username}    IP: {local_ip}    Ping: {latency:.0f}ms"

                if latency < 50:
                    item.setForeground(QColor("#2ecc71"))  # Green
                elif latency < 100:
                    item.setForeground(QColor("#f39c12"))  # Orange
                else:
                    item.setForeground(QColor("#e74c3c"))  # Red

                item.setText(text)
                break

    # ─── Logging ────────────────────────────────────────────────────────────────

    def _append_log(self, message: str):
        """Append to home page log."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def _room_log(self, message: str):
        """Append to room page log."""
        timestamp = time.strftime("%H:%M:%S")
        self.room_log_text.append(f"[{timestamp}] {message}")

    # ─── Cleanup ────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Clean up on window close."""
        if self.is_connected:
            self._disconnect()
        self.async_worker.stop()
        event.accept()


# ─── Entry Point ────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    window = GameVPNApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
