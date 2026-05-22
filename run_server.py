"""
GameVPN - Launch Signaling Server
==================================
Run: python run_server.py
Deploy free on Render/Railway with this as entry point.
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("  GameVPN Signaling Server")
    print("  Listening on port 8765")
    print("=" * 50)
    uvicorn.run(
        "server.signaling_server:app",
        host="0.0.0.0",
        port=8765,
        log_level="info",
        reload=False,
    )
