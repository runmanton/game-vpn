"""
GameVPN - Launch Signaling Server
==================================
Run: python run_server.py
Deploy free on Render/Railway with this as entry point.
Honors the PORT env var (required by Render/Railway/Fly).
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print("=" * 50)
    print("  GameVPN Signaling Server")
    print(f"  Listening on port {port}")
    print("=" * 50)
    uvicorn.run(
        "server.signaling_server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
