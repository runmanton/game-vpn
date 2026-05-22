# GameVPN - Virtual LAN for Gaming

## Tong quan

GameVPN la ung dung tao mang LAN ao (Virtual LAN) cho phep nguoi choi o cac quoc gia khac nhau ket noi va choi game cung nhau nhu dang o mang noi bo. Ung dung su dung WireGuard lam giao thuc VPN voi kien truc Hybrid (P2P + Relay).

## Kien truc

```
Player A  <──WebSocket──>  Signaling Server  <──WebSocket──>  Player B
   |                                                              |
   └──────────── WireGuard Tunnel (P2P / Relay) ─────────────────┘
                        10.10.0.0/24
```

### Thanh phan chinh

| Thanh phan | File | Mo ta |
|------------|------|-------|
| Signaling Server | `server/signaling_server.py` | FastAPI + WebSocket. Quan ly phong, trao doi key, phat hien peer |
| VPN Engine | `engine/vpn_engine.py` | WireGuard key gen, STUN NAT traversal, tunnel management |
| Client | `client/vpn_client.py` | WebSocket client giao tiep voi signaling server |
| GUI | `client/gui.py` | PyQt6 dark-theme desktop app |
| Entry point | `run_client.py` | Khoi chay ung dung client |
| Server entry | `run_server.py` | Khoi chay signaling server |

## Cong nghe su dung

- **Giao thuc VPN**: WireGuard (ChaCha20-Poly1305 encryption)
- **NAT Traversal**: STUN (RFC 5389) voi Google STUN servers
- **Signaling**: FastAPI + WebSocket
- **GUI**: PyQt6 (dark theme)
- **Build**: PyInstaller (.exe) + Inno Setup (installer)
- **Deploy server**: Docker / Render.com / Railway.app / Fly.io

## Cau truc thu muc

```
game-vpn/
├── server/
│   ├── __init__.py
│   └── signaling_server.py    # FastAPI WebSocket signaling server
├── engine/
│   ├── __init__.py
│   └── vpn_engine.py          # WireGuard + STUN + tunnel management
├── client/
│   ├── __init__.py
│   ├── vpn_client.py          # WebSocket signaling client
│   └── gui.py                 # PyQt6 GUI (dark theme)
├── installer/
│   ├── GameVPN_Setup.iss       # Inno Setup script
│   └── license.txt             # MIT License
├── run_client.py               # Client entry point
├── run_server.py               # Server entry point
├── BUILD_INSTALLER.bat         # Build full installer (exe + WireGuard + PDF)
├── INSTALL_AND_RUN.bat         # Quick install dependencies & run
├── PUSH_TO_GITHUB.bat          # Push project to GitHub
├── Dockerfile                  # Docker deploy for signaling server
├── requirements.txt            # Python dependencies
├── GameVPN_Manual.pdf          # User manual (Vietnamese)
└── README.md
```

## Luong hoat dong

1. **Tao phong**: Host tao phong → nhan Room Code (vd: `XKCD-5678`)
2. **Tham gia**: Nguoi choi nhap Room Code → tu dong ket noi VPN
3. **Mang LAN ao**: Moi nguoi nhan IP `10.10.0.x` → choi game nhu LAN
4. **Ngat ket noi**: Click "Disconnect" hoac dong app

## Mang Virtual LAN

- Subnet: `10.10.0.0/24`
- Host: `10.10.0.1`
- Player 2: `10.10.0.2`, Player 3: `10.10.0.3`, ...
- Toi da: 20 nguoi/phong (khuyen nghi < 10)

## Cai dat & Chay

### Cach 1: Dung Installer (Khuyen dung)

Chay `BUILD_INSTALLER.bat` de tao file `installer/output/GameVPN_Setup.exe`.
File nay dong goi:
- GameVPN.exe
- WireGuard (tu cai ngam)
- User Manual PDF
- Desktop shortcut

Gui `GameVPN_Setup.exe` cho ban be, ho chi can double-click va Next la xong.

### Cach 2: Chay tu source

```bash
pip install -r requirements.txt
python run_client.py
```

### Deploy Signaling Server

```bash
# Docker
docker build -t gamevpn-server .
docker run -p 8765:8765 gamevpn-server

# Hoac deploy len Render.com / Railway.app / Fly.io
```

## Yeu cau he thong

- Windows 10/11 (64-bit)
- WireGuard (duoc cai tu dong qua installer)
- Quyen Administrator (de tao VPN tunnel)
- Ket noi internet

## Bao mat

- Ma hoa: WireGuard ChaCha20-Poly1305
- Key exchange: Curve25519
- Moi phien tao key pair moi (khong luu tru)
- Room code ngau nhien, tu xoa sau khi tat ca roi phong

## License

MIT License - Xem file `installer/license.txt`
WireGuard is licensed under GPLv2.
