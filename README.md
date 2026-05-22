# 🎮 GameVPN — Virtual LAN for Gaming

Chơi game LAN cùng bạn bè ở khắp nơi trên thế giới, như thể ngồi cùng phòng!

GameVPN tạo mạng LAN ảo (virtual LAN) sử dụng WireGuard, kết nối P2P trực tiếp giữa các máy với relay fallback khi cần.

---

## Cách hoạt động

```
Bạn (Việt Nam) ←──P2P──→ Bạn bè (Nhật Bản)
       ↑                        ↑
       └──── Relay Server ──────┘  (fallback khi P2P không được)
```

1. **Signaling Server** phối hợp kết nối ban đầu (trao đổi key, tìm IP)
2. **STUN** phát hiện IP public và loại NAT
3. **WireGuard** tạo tunnel VPN mã hóa, hiệu suất cao
4. Mỗi người được cấp IP LAN ảo (10.10.0.x) → game thấy như mạng nội bộ

---

## Cài đặt nhanh

### Bước 1: Cài Python + Dependencies

```bash
# Cần Python 3.10+
pip install -r requirements.txt
```

### Bước 2: Cài WireGuard

Tải và cài WireGuard từ: https://www.wireguard.com/install/

### Bước 3: Chạy Signaling Server

Một người trong nhóm chạy server (hoặc deploy lên cloud miễn phí):

```bash
python run_server.py
```

Server sẽ chạy trên port 8765.

### Bước 4: Chạy Client

Mỗi người chạy app client:

```bash
python run_client.py
```

---

## Sử dụng

### Người tạo phòng:
1. Mở app → Nhập tên → Nhập server URL
2. Click **Create Room**
3. Chia sẻ **Room Code** (ví dụ: `XKCD-5678`) cho bạn bè

### Người tham gia:
1. Mở app → Nhập tên → Nhập server URL
2. Nhập Room Code → Click **Join Room**
3. Đợi kết nối VPN thiết lập

### Chơi game:
- Mở game → tìm **LAN/Local Network** → sẽ thấy các bạn cùng phòng!
- IP LAN ảo hiển thị trong app (ví dụ: 10.10.0.2)

---

## Deploy Server miễn phí

### Render.com (Khuyên dùng)
1. Push code lên GitHub
2. Tạo **Web Service** trên render.com
3. Build command: `pip install fastapi uvicorn[standard] websockets`
4. Start command: `python run_server.py`
5. Dùng URL được cấp làm Server URL trong app

### Railway.app
1. Push lên GitHub → Connect repo trên Railway
2. Railway tự detect Dockerfile và deploy

### Docker
```bash
docker build -t gamevpn-server .
docker run -p 8765:8765 gamevpn-server
```

---

## Build installer (chia sẻ cho bạn bè không cần cài Python)

Chạy `BUILD_INSTALLER.bat` (yêu cầu Python 3.10+ và Inno Setup 6). Script sẽ:
1. Build `dist/GameVPN.exe` bằng PyInstaller
2. Tải WireGuard MSI
3. Đóng gói thành `installer/output/GameVPN_Setup.exe` bằng Inno Setup

Gửi `GameVPN_Setup.exe` cho bạn bè — họ chỉ cần double-click và Next.

---

## Cấu trúc project

```
game-vpn/
├── run_client.py            # Khởi chạy app client
├── run_server.py            # Khởi chạy signaling server
├── BUILD_INSTALLER.bat      # Build installer (.exe + WireGuard + PDF)
├── INSTALL_AND_RUN.bat      # Cài deps & chạy từ source
├── PUSH_TO_GITHUB.bat       # Push code lên GitHub
├── requirements.txt         # Dependencies
├── Dockerfile               # Docker cho server
├── client/
│   ├── gui.py               # Giao diện PyQt6
│   └── vpn_client.py        # WebSocket client
├── engine/
│   └── vpn_engine.py        # WireGuard + STUN + Relay
├── server/
│   └── signaling_server.py  # FastAPI signaling server
├── installer/
│   ├── GameVPN_Setup.iss    # Inno Setup script
│   └── license.txt          # MIT License
└── assets/                  # Icons, images
```

---

## Yêu cầu hệ thống

- Windows 10/11
- Python 3.10+ (hoặc dùng file .exe)
- WireGuard (tải từ wireguard.com)
- Quyền Administrator (để tạo network interface)

---

## Troubleshooting

| Vấn đề | Giải pháp |
|---------|-----------|
| Không kết nối được server | Kiểm tra URL server, firewall |
| VPN tunnel không hoạt động | Cài WireGuard, chạy với quyền Admin |
| Ping cao giữa các peer | NAT symmetric → sẽ dùng relay, tốc độ phụ thuộc server |
| Game không thấy peer | Kiểm tra game hỗ trợ LAN, thử ping IP trong app |
