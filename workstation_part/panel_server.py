#!/usr/bin/env python3
"""
Control Panel companion server.
Run with:  python3 server.py
Then open: http://localhost:8765
"""

import http.server
import json
import pathlib
import socketserver
import sys
import argparse
import requests

PORT = 8765
PANEL_HTML = pathlib.Path(__file__).parent / "panel.html"

# Remote Pi configurations (will be overridden via CLI args)
PI_REMOTE_ENABLED = False
PI_IP = "192.168.2.2"
PI_PORT = 5006



class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"  {self.address_string()}  {format % args}")

    # ── routing ──────────────────────────────────────────────────────────────

    def do_GET(self):
        if self.path in ("/", "/panel.html"):
            self._serve_file()
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        body = self._read_body()
        if self.path == "/api/touch":
            self._touch(body)
        elif self.path == "/api/remove":
            self._remove(body)
        elif self.path == "/api/listdir":
            self._listdir(body)
        else:
            self._respond(404, {"error": "unknown endpoint"})

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── file operations ───────────────────────────────────────────────────────

    def _touch(self, body):
        if PI_REMOTE_ENABLED:
            try:
                r = requests.post(f"http://{PI_IP}:{PI_PORT}/api/touch", json=body, timeout=3.0)
                return self._respond(r.status_code, r.json())
            except Exception as e:
                return self._respond(502, {"error": f"Cannot reach Pi server: {e}"})

        dir_path = body.get("dir", "")
        name     = body.get("name", "")
        if not dir_path or not name:
            return self._respond(400, {"error": "dir and name required"})
        try:
            target = pathlib.Path(dir_path) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            print(f"  TOUCH  {target}")
            self._respond(200, {"ok": True, "path": str(target)})
        except Exception as e:
            print(f"  ERROR  {e}")
            self._respond(500, {"error": str(e)})

    def _listdir(self, body):
        if PI_REMOTE_ENABLED:
            try:
                r = requests.post(f"http://{PI_IP}:{PI_PORT}/api/listdir", json=body, timeout=3.0)
                return self._respond(r.status_code, r.json())
            except Exception as e:
                return self._respond(502, {"error": f"Cannot reach Pi server: {e}"})

        dir_path = body.get("dir", "")
        if not dir_path:
            return self._respond(400, {"error": "dir required"})
        try:
            p = pathlib.Path(dir_path)
            if not p.is_dir():
                return self._respond(200, {"files": []})
            sorted_files = sorted([f for f in p.iterdir() if f.is_file()], key=lambda f: f.stat().st_mtime)
            files = [f.name for f in sorted_files]
            self._respond(200, {"files": files})
        except Exception as e:
            print(f"  ERROR  {e}")
            self._respond(500, {"error": str(e)})

    def _remove(self, body):
        if PI_REMOTE_ENABLED:
            try:
                r = requests.post(f"http://{PI_IP}:{PI_PORT}/api/remove", json=body, timeout=3.0)
                return self._respond(r.status_code, r.json())
            except Exception as e:
                return self._respond(502, {"error": f"Cannot reach Pi server: {e}"})

        dir_path = body.get("dir", "")
        name     = body.get("name", "")
        if not dir_path or not name:
            return self._respond(400, {"error": "dir and name required"})
        try:
            target = pathlib.Path(dir_path) / name
            if target.exists():
                target.unlink()
                print(f"  REMOVE {target}")
            self._respond(200, {"ok": True})
        except Exception as e:
            print(f"  ERROR  {e}")
            self._respond(500, {"error": str(e)})


    # ── helpers ───────────────────────────────────────────────────────────────

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw    = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _serve_file(self):
        try:
            html = PANEL_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self._cors()
            self.end_headers()
            self.wfile.write(html)
        except FileNotFoundError:
            self._respond(404, {"error": "panel.html not found next to server.py"})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def verify_pi_connection(ip: str, port: int):
    url = f"http://{ip}:{port}/api/metrics"
    print(f"[PANEL] Validating connection to Raspberry Pi at {url}...")
    try:
        r = requests.get(url, timeout=3.0)
        if r.status_code == 200:
            print("[PANEL] Successfully connected to Raspberry Pi.")
            return True
        else:
            print(f"[PANEL] ERROR: Pi server returned status code {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"[PANEL] ERROR: Cannot reach Raspberry Pi at {url}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if not PANEL_HTML.exists():
        print(f"ERROR: panel.html not found at {PANEL_HTML}")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", help="IP address of the remote Raspberry Pi")
    parser.add_argument("--port", type=int, default=8765, help="Port to run panel server locally")
    args = parser.parse_args()

    PORT = args.port if args.port else 8765

    if args.remote:
        PI_REMOTE_ENABLED = True
        PI_IP = args.remote
        verify_pi_connection(PI_IP, PI_PORT)
        print(f"OrbiOS Workstation Panel running in REMOTE mode (Pi: {PI_IP}:{PI_PORT}) at http://localhost:{PORT}")
    else:
        print(f"OrbiOS Workstation Panel running in LOCAL mode at http://localhost:{PORT}")

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Open in Firefox:  http://localhost:{PORT}")
        print("Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

