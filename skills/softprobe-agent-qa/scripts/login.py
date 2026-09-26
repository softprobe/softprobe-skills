#!/usr/bin/env python3
"""Human-only Explorer login via browser loopback (stdlib).

Opens Explorer /auth/cli, which redirects tokens to a local callback.
Agents must not run this; ask the human to run it when credentials are missing.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import pathlib
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from typing import Any

_SCRIPTS = pathlib.Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from credentials import (  # noqa: E402
    DEFAULT_EXPLORER_BASE,
    mask_token,
    save_credentials,
)


SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Softprobe login</title>
<style>
body{font-family:system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem;color:#111}
h1{font-size:1.4rem}p{line-height:1.5;color:#333}
</style></head>
<body>
<h1>Signed in to Softprobe</h1>
<p>You can close this tab and return to your coding agent.</p>
</body></html>
"""

ERROR_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Softprobe login failed</title></head>
<body><h1>Login failed</h1><p>{msg}</p></body></html>
"""


def pick_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return int(sock.getsockname()[1])
            except OSError:
                continue
    raise RuntimeError("could not bind loopback port")


def open_browser(url: str) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", url], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", url], check=False)
        else:
            webbrowser.open(url)
    except OSError:
        webbrowser.open(url)


def run_loopback(port: int, timeout_sec: int = 300) -> dict[str, Any]:
    result: dict[str, Any] = {}
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.rstrip("/") != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            access = (qs.get("access_token") or [""])[0].strip()
            refresh = (qs.get("refresh_token") or [""])[0].strip()
            email = (qs.get("email") or [""])[0].strip()
            expires_raw = (qs.get("expires_at") or [""])[0].strip()
            if not access:
                body = ERROR_HTML.format(msg="Missing access_token")
                data = body.encode()
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                result["error"] = "missing access_token"
                done.set()
                return
            expires_at = int(expires_raw) if expires_raw.isdigit() else None
            result.update(
                {
                    "access_token": access,
                    "refresh_token": refresh or None,
                    "email": email or None,
                    "expires_at": expires_at,
                }
            )
            data = SUCCESS_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            done.set()

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not done.wait(timeout_sec):
            raise TimeoutError(
                f"Timed out after {timeout_sec}s waiting for Explorer login callback"
            )
    finally:
        server.shutdown()
    if result.get("error"):
        raise RuntimeError(result["error"])
    if not result.get("access_token"):
        raise RuntimeError("login callback produced no access token")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--explorer-base",
        default=os.environ.get("SOFTPROBE_EXPLORER_BASE", DEFAULT_EXPLORER_BASE),
        help="Explorer origin (default: production)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Preferred loopback port")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the login URL instead of opening a browser",
    )
    args = parser.parse_args()

    port = pick_port(args.port)
    base = args.explorer_base.rstrip("/")
    login_url = f"{base}/auth/cli?port={port}"
    print(f"Waiting for Explorer login on http://127.0.0.1:{port}/callback", flush=True)
    print(f"Open: {login_url}", flush=True)
    if not args.no_browser:
        open_browser(login_url)

    tokens = run_loopback(port, timeout_sec=args.timeout)
    path = save_credentials(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_at=tokens.get("expires_at"),
        email=tokens.get("email"),
        explorer_base=base,
    )
    print(f"Saved credentials to {path}", flush=True)
    print(f"Token preview: {mask_token(tokens['access_token'])}", flush=True)
    if tokens.get("email"):
        print(f"Email: {tokens['email']}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError) as error:
        print(f"login: {error}", file=sys.stderr)
        sys.exit(1)
