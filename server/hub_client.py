"""Client for the GameVPN WireGuard hub management API.

The signaling server calls this whenever a peer joins / leaves a room, so
the hub VM can add or remove the peer's WireGuard public key dynamically.

Hub address + auth token come from env vars (`HUB_API_URL`, `HUB_API_TOKEN`).
If either is missing the client logs a warning and becomes a no-op so the
signaling server still works in legacy/direct-P2P mode.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("GameVPN-Hub")

HUB_API_URL = os.environ.get("HUB_API_URL", "").rstrip("/")
HUB_API_TOKEN = os.environ.get("HUB_API_TOKEN", "")
HUB_PUBLIC_KEY = os.environ.get("HUB_PUBLIC_KEY", "")
HUB_ENDPOINT = os.environ.get("HUB_ENDPOINT", "")
HUB_TIMEOUT = float(os.environ.get("HUB_API_TIMEOUT", "5"))


def is_enabled() -> bool:
    return bool(HUB_API_URL and HUB_API_TOKEN)


async def fetch_info() -> Optional[dict]:
    """Return hub public key + endpoint for clients to attach to.

    Pulls from HUB_PUBLIC_KEY + HUB_ENDPOINT env vars if set (preferred --
    avoids a per-room HTTP round-trip and degrades to None instead of
    crashing the client when the hub is briefly unreachable). Falls back
    to GET {HUB_API_URL}/info if the env vars are missing.
    """
    if HUB_PUBLIC_KEY and HUB_ENDPOINT:
        return {"public_key": HUB_PUBLIC_KEY, "endpoint": HUB_ENDPOINT}
    if not HUB_API_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=HUB_TIMEOUT) as client:
            r = await client.get(f"{HUB_API_URL}/info")
            r.raise_for_status()
            data = r.json()
            logger.info(f"Hub info fetched live: endpoint={data.get('endpoint')}")
            return data
    except Exception as e:
        logger.warning(f"Failed to fetch hub /info: {e}")
        return None


async def add_peer(public_key: str, ip: str) -> bool:
    """Register a client's WireGuard pubkey with the hub. Returns True on success."""
    if not is_enabled():
        return False
    try:
        async with httpx.AsyncClient(timeout=HUB_TIMEOUT) as client:
            r = await client.post(
                f"{HUB_API_URL}/peer/add",
                headers={"Authorization": f"Bearer {HUB_API_TOKEN}"},
                json={"public_key": public_key, "ip": ip},
            )
            if r.status_code == 200:
                logger.info(f"Hub: added peer {public_key[:12]}... -> {ip}")
                return True
            logger.warning(f"Hub add_peer failed {r.status_code}: {r.text}")
            return False
    except Exception as e:
        logger.warning(f"Hub add_peer error: {e}")
        return False


async def remove_peer(public_key: str) -> bool:
    """Remove a client from the hub. Returns True on success."""
    if not is_enabled():
        return False
    try:
        async with httpx.AsyncClient(timeout=HUB_TIMEOUT) as client:
            r = await client.post(
                f"{HUB_API_URL}/peer/remove",
                headers={"Authorization": f"Bearer {HUB_API_TOKEN}"},
                json={"public_key": public_key},
            )
            if r.status_code == 200:
                logger.info(f"Hub: removed peer {public_key[:12]}...")
                return True
            logger.warning(f"Hub remove_peer failed {r.status_code}: {r.text}")
            return False
    except Exception as e:
        logger.warning(f"Hub remove_peer error: {e}")
        return False
