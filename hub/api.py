"""GameVPN WireGuard hub management API.

Runs on the relay VM. Authenticates incoming requests with a bearer token
and dynamically adds / removes WireGuard peers on the wg0 interface so
GameVPN clients can route their virtual-LAN traffic through this hub.

Endpoints:
  GET  /info          -> {public_key, endpoint}                (public)
  POST /peer/add      -> body {public_key, ip}                  (auth)
  POST /peer/remove   -> body {public_key}                      (auth)
  GET  /peers         -> [{public_key, allowed_ips, ...}]       (auth)

Auth: header `Authorization: Bearer <api_token>`.
"""
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG_PATH = "/etc/gamevpn-hub/config.json"
WG_INTERFACE = "wg0"
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8080

with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

TOKEN = CONFIG["api_token"]
HUB_PUBLIC_KEY = CONFIG["hub_public_key"]
HUB_ENDPOINT = CONFIG["hub_endpoint"]


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


def add_peer(public_key: str, ip: str):
    result = _run([
        "wg", "set", WG_INTERFACE,
        "peer", public_key,
        "allowed-ips", f"{ip}/32",
        "persistent-keepalive", "25",
    ])
    return result.returncode == 0, result.stderr.strip()


def remove_peer(public_key: str):
    result = _run([
        "wg", "set", WG_INTERFACE,
        "peer", public_key, "remove",
    ])
    return result.returncode == 0, result.stderr.strip()


def list_peers():
    result = _run(["wg", "show", WG_INTERFACE, "dump"])
    if result.returncode != 0:
        return []
    peers = []
    lines = result.stdout.strip().split("\n")
    # First line is the interface row, skip it.
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        peers.append({
            "public_key": parts[0],
            "endpoint": parts[2],
            "allowed_ips": parts[3],
            "latest_handshake": int(parts[4]) if parts[4].isdigit() else 0,
            "rx_bytes": int(parts[5]) if parts[5].isdigit() else 0,
            "tx_bytes": int(parts[6]) if parts[6].isdigit() else 0,
        })
    return peers


class Handler(BaseHTTPRequestHandler):
    def _auth_ok(self):
        return self.headers.get("Authorization", "") == f"Bearer {TOKEN}"

    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_GET(self):
        if self.path == "/info":
            return self._send(200, {
                "public_key": HUB_PUBLIC_KEY,
                "endpoint": HUB_ENDPOINT,
            })
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        if self.path == "/peers":
            return self._send(200, list_peers())
        if self.path == "/health":
            return self._send(200, {"ok": True, "ts": int(time.time())})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        try:
            body = self._read_body()
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid json"})

        if self.path == "/peer/add":
            pk = body.get("public_key")
            ip = body.get("ip")
            if not pk or not ip:
                return self._send(400, {"error": "missing public_key or ip"})
            ok, err = add_peer(pk, ip)
            return self._send(200 if ok else 500, {"ok": ok, "error": err or None})

        if self.path == "/peer/remove":
            pk = body.get("public_key")
            if not pk:
                return self._send(400, {"error": "missing public_key"})
            ok, err = remove_peer(pk)
            return self._send(200, {"ok": ok, "error": err or None})

        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")


def main():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(f"GameVPN hub API listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
