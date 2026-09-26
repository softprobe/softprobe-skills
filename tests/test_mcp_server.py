#!/usr/bin/env python3
"""MCP stdio framing smoke tests (no network)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "skills" / "softprobe-agent-qa" / "scripts" / "mcp_server.py"


def _frame_lsp(payload: dict) -> bytes:
    raw = json.dumps(payload).encode("utf-8")
    return f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw


def _frame_ndjson(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8") + b"\n"


def _read_lsp_frames(buf: bytes) -> list[dict]:
    out: list[dict] = []
    i = 0
    while i < len(buf):
        header_end = buf.find(b"\r\n\r\n", i)
        if header_end < 0:
            break
        headers = buf[i:header_end].decode("ascii", errors="replace")
        length = None
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
        if length is None:
            break
        start = header_end + 4
        end = start + length
        if end > len(buf):
            break
        out.append(json.loads(buf[start:end].decode("utf-8")))
        i = end
    return out


def _read_ndjson_frames(buf: bytes) -> list[dict]:
    return [json.loads(line) for line in buf.splitlines() if line.strip()]


class McpServerTests(unittest.TestCase):
    def _run(self, reqs: bytes) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(SERVER)],
            input=reqs,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def test_content_length_initialize_and_tools_list(self) -> None:
        reqs = b"".join(
            [
                _frame_lsp(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "0"},
                        },
                    }
                ),
                _frame_lsp({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                _frame_lsp({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            ]
        )
        proc = self._run(reqs)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        frames = _read_lsp_frames(proc.stdout)
        self.assertGreaterEqual(len(frames), 2)
        init = next(f for f in frames if f.get("id") == 1)
        self.assertEqual(init["result"]["serverInfo"]["name"], "softprobe-agent-qa")
        tools = next(f for f in frames if f.get("id") == 2)
        names = {t["name"] for t in tools["result"]["tools"]}
        self.assertIn("get_session", names)
        self.assertIn("whoami", names)

    def test_ndjson_claude_code_initialize(self) -> None:
        """Claude Code speaks newline-delimited JSON (not Content-Length)."""
        reqs = b"".join(
            [
                _frame_ndjson(
                    {
                        "jsonrpc": "2.0",
                        "id": 0,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {"roots": {}},
                            "clientInfo": {"name": "claude-code", "version": "2"},
                        },
                    }
                ),
                _frame_ndjson({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                _frame_ndjson({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            ]
        )
        proc = self._run(reqs)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        frames = _read_ndjson_frames(proc.stdout)
        self.assertGreaterEqual(len(frames), 2)
        init = next(f for f in frames if f.get("id") == 0)
        self.assertEqual(init["result"]["protocolVersion"], "2025-11-25")
        tools = next(f for f in frames if f.get("id") == 1)
        self.assertTrue(any(t["name"] == "search_sessions" for t in tools["result"]["tools"]))


if __name__ == "__main__":
    unittest.main()
