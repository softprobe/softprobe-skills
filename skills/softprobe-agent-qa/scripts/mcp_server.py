#!/usr/bin/env python3
"""Softprobe Agent QA MCP server (stdio, stdlib only).

Exposes the same read-only Explorer gateway tools as softprobe_api.py.
Never print diagnostics on stdout — MCP owns that stream; use stderr.
"""

from __future__ import annotations

import json
import sys
import pathlib
from typing import Any

_SCRIPTS = pathlib.Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from credentials import MissingCredentialsError  # noqa: E402
from softprobe_api import ApiError, call  # noqa: E402

# Prefer the client's negotiated version when known; fall back for older hosts.
SUPPORTED_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "softprobe-agent-qa"
SERVER_VERSION = "0.2.0"

# MCP tool name -> softprobe_api.call command
_TOOL_COMMAND = {
    "whoami": "whoami",
    "list_workspaces": "list-workspaces",
    "select_workspace": "select-workspace",
    "search_sessions": "search-sessions",
    "get_session": "get-session",
    "get_session_observations": "get-session-observations",
    "search_observations": "search-observations",
    "get_observation": "get-observation",
    "get_trace": "get-trace",
    "logs_by_session": "logs-by-session",
    "logs_by_trace": "logs-by-trace",
}


def _prop(type_: str, description: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"type": type_, "description": description}
    out.update(extra)
    return out


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return {
        "name": name,
        "description": description,
        "inputSchema": schema,
        "annotations": {
            "title": name.replace("_", " ").title(),
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    }


TOOLS: list[dict[str, Any]] = [
    _tool("whoami", "Check Explorer login and list workspaces (no token leaked).", {}),
    _tool("list_workspaces", "List Softprobe workspaces for the signed-in user.", {}),
    _tool(
        "select_workspace",
        "Select the active workspace (needed when API returns workspace_picker_required).",
        {"workspace_id": _prop("string", "Workspace id to select")},
        ["workspace_id"],
    ),
    _tool(
        "search_sessions",
        "Search Agent QA sessions in a UTC time window.",
        {
            "from_time": _prop("string", "ISO-8601 UTC start, e.g. 2026-01-01T00:00:00Z"),
            "to_time": _prop("string", "ISO-8601 UTC end"),
            "limit": _prop("integer", "Max results (default 50)"),
            "cursor": _prop("string", "Pagination cursor"),
            "agent_name": _prop("string", "Filter by agent name"),
        },
        ["from_time", "to_time"],
    ),
    _tool(
        "get_session",
        "Get one session by session_id.",
        {
            "session_id": _prop("string", "Session id"),
            "limit": _prop("integer", "Observation page size (default 200)"),
        },
        ["session_id"],
    ),
    _tool(
        "get_session_observations",
        "List observations for a session.",
        {
            "session_id": _prop("string", "Session id"),
            "limit": _prop("integer", "Max results (default 200)"),
            "cursor": _prop("string", "Pagination cursor"),
        },
        ["session_id"],
    ),
    _tool(
        "search_observations",
        "Search observations in a UTC time window.",
        {
            "from_time": _prop("string", "ISO-8601 UTC start"),
            "to_time": _prop("string", "ISO-8601 UTC end"),
            "session_id": _prop("string", "Optional session filter"),
            "observation_types": _prop(
                "string",
                "Comma-separated types: agent,generation,tool,span,...",
            ),
            "limit": _prop("integer", "Max results"),
            "cursor": _prop("string", "Pagination cursor"),
        },
        ["from_time", "to_time"],
    ),
    _tool(
        "get_observation",
        "Get one observation/span by span_id.",
        {"span_id": _prop("string", "Span / observation id")},
        ["span_id"],
    ),
    _tool(
        "get_trace",
        "Get a trace and its spans by trace_id.",
        {
            "trace_id": _prop("string", "Trace id"),
            "limit": _prop("integer", "Max spans (default 200)"),
            "cursor": _prop("string", "Pagination cursor"),
        },
        ["trace_id"],
    ),
    _tool(
        "logs_by_session",
        "Fetch correlated logs for a session (fixed SQL template).",
        {"session_id": _prop("string", "Session id")},
        ["session_id"],
    ),
    _tool(
        "logs_by_trace",
        "Fetch correlated logs for a trace (fixed SQL template).",
        {"trace_id": _prop("string", "Trace id")},
        ["trace_id"],
    ),
]


# Claude Code speaks newline-delimited JSON; Cursor/LSP-style clients use
# Content-Length framing. Detect from the first message and mirror back.
_framing: str | None = None  # "ndjson" | "content-length"


def _read_message() -> dict[str, Any] | None:
    global _framing
    line = sys.stdin.buffer.readline()
    if not line:
        return None

    # First non-empty line decides framing when still unknown.
    stripped = line.strip()
    if not stripped:
        return _read_message()

    if stripped.startswith(b"{") or _framing == "ndjson":
        _framing = "ndjson"
        return json.loads(stripped.decode("utf-8"))

    # Content-Length header (possibly after we already saw headers mid-message)
    _framing = "content-length"
    headers: dict[str, str] = {}
    raw = line.decode("utf-8", errors="replace").strip()
    if ":" in raw:
        key, value = raw.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    while True:
        next_line = sys.stdin.buffer.readline()
        if not next_line:
            return None
        if next_line in (b"\r\n", b"\n"):
            break
        raw = next_line.decode("utf-8", errors="replace").strip()
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    length_s = headers.get("content-length")
    if not length_s:
        return None
    length = int(length_s)
    body = sys.stdin.buffer.read(length)
    if len(body) < length:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _framing == "ndjson":
        sys.stdout.buffer.write(raw + b"\n")
    else:
        sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def _result(req_id: Any, result: Any) -> None:
    _write_message({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id: Any, code: int, message: str) -> None:
    _write_message(
        {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    )


def _tool_text(data: Any, *, is_error: bool = False) -> dict[str, Any]:
    text = data if isinstance(data, str) else json.dumps(data, indent=2, sort_keys=True)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def _handle_tools_call(arguments: dict[str, Any] | None, name: str) -> dict[str, Any]:
    command = _TOOL_COMMAND.get(name)
    if not command:
        return _tool_text(f"Unknown tool: {name}", is_error=True)
    args = dict(arguments or {})
    try:
        status, result = call(command, **args)
    except MissingCredentialsError as err:
        return _tool_text(
            f"{err}\nAsk the human to run: python3 {_SCRIPTS / 'login.py'}",
            is_error=True,
        )
    except (ApiError, OSError, ValueError, RuntimeError, TypeError, KeyError) as err:
        return _tool_text(str(err), is_error=True)
    if not (200 <= status < 300):
        return _tool_text({"status": status, "body": result}, is_error=True)
    return _tool_text(result)


def _dispatch(msg: dict[str, Any]) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications have no id
    if req_id is None:
        return

    if method == "initialize":
        requested = ""
        if isinstance(params, dict):
            requested = str(params.get("protocolVersion") or "")
        version = (
            requested
            if requested in SUPPORTED_PROTOCOL_VERSIONS
            else DEFAULT_PROTOCOL_VERSION
        )
        if requested and requested not in SUPPORTED_PROTOCOL_VERSIONS:
            # Accept unknown newer versions by echoing them back — hosts
            # often only need tools/list + tools/call.
            version = requested
        _result(
            req_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
        return

    if method == "ping":
        _result(req_id, {})
        return

    if method == "tools/list":
        _result(req_id, {"tools": TOOLS})
        return

    if method == "tools/call":
        name = params.get("name") if isinstance(params, dict) else None
        arguments = params.get("arguments") if isinstance(params, dict) else {}
        if not isinstance(name, str):
            _error(req_id, -32602, "tools/call requires name")
            return
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            _error(req_id, -32602, "arguments must be an object")
            return
        _result(req_id, _handle_tools_call(arguments, name))
        return

    _error(req_id, -32601, f"Method not found: {method}")


def main() -> int:
    while True:
        try:
            msg = _read_message()
        except (OSError, json.JSONDecodeError, ValueError) as err:
            print(f"softprobe mcp: read error: {err}", file=sys.stderr)
            return 1
        if msg is None:
            return 0
        try:
            _dispatch(msg)
        except Exception as err:  # noqa: BLE001 — keep server alive per request
            print(f"softprobe mcp: {err}", file=sys.stderr)
            req_id = msg.get("id") if isinstance(msg, dict) else None
            if req_id is not None:
                _error(req_id, -32603, str(err))


if __name__ == "__main__":
    raise SystemExit(main())
