#!/usr/bin/env python3
"""Read-only Softprobe Explorer gateway client (stdlib only).

Routes lake reads through https://explorer.softprobe.ai/api/thelake using the
user's Explorer session (Bearer). Never sends X-Softprobe-Assertion.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_SCRIPTS = pathlib.Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from credentials import (  # noqa: E402
    DEFAULT_EXPLORER_BASE,
    MissingCredentialsError,
    access_token_near_expiry,
    load_credentials,
)

WORKSPACE_PICKER_CODE = "workspace_picker_required"


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def explorer_base(creds: dict[str, Any] | None = None) -> str:
    env = os.environ.get("SOFTPROBE_EXPLORER_BASE", "").strip()
    if env:
        return env.rstrip("/")
    if creds and creds.get("explorer_base"):
        return str(creds["explorer_base"]).rstrip("/")
    return DEFAULT_EXPLORER_BASE


def _http(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: Any = None,
    timeout: int = 60,
) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            detail: Any = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = raw.decode(errors="replace")
        raise ApiError(
            f"{method} {url}: HTTP {error.code}: {detail}",
            status=error.code,
            body=detail,
        ) from error


def try_refresh(creds: dict[str, Any]) -> dict[str, Any]:
    refresh = (creds.get("refresh_token") or "").strip()
    if not refresh:
        return creds
    # Explorer does not expose a public refresh endpoint for CLI yet.
    # Prefer re-login when access token expires; keep hook for future.
    return creds


def bearer_token() -> tuple[str, dict[str, Any]]:
    creds = load_credentials()
    if access_token_near_expiry(creds):
        creds = try_refresh(creds)
        if access_token_near_expiry(creds):
            raise MissingCredentialsError(
                "Explorer access token expired. Ask the human to run login.py again."
            )
    token = str(creds["access_token"]).strip()
    return token, creds


def gateway_request(
    method: str,
    path: str,
    payload: Any = None,
    *,
    auto_workspace: bool = True,
) -> tuple[int, Any]:
    token, creds = bearer_token()
    base = explorer_base(creds)
    url = f"{base}{path if path.startswith('/') else '/' + path}"
    try:
        return _http(method, url, token=token, payload=payload)
    except ApiError as err:
        if (
            auto_workspace
            and err.status == 409
            and isinstance(err.body, dict)
            and err.body.get("code") == WORKSPACE_PICKER_CODE
        ):
            raise ApiError(
                "Multiple workspaces — run: softprobe_api.py select-workspace <workspace_id> "
                "(list with softprobe_api.py list-workspaces)",
                status=409,
                body=err.body,
            ) from err
        raise


def lake_path(suffix: str) -> str:
    s = suffix if suffix.startswith("/") else f"/{suffix}"
    if s.startswith("/api/thelake"):
        return s
    if s.startswith("/v1/"):
        return f"/api/thelake{s}"
    return f"/api/thelake/v1{s if s.startswith('/') else '/' + s}"


def query_string(values: dict[str, Any]) -> str:
    return "?" + urllib.parse.urlencode(
        {k: v for k, v in values.items() if v is not None}
    )


def sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def call(command: str, **kwargs: Any) -> tuple[int, Any]:
    """Run a named API command. Shared by CLI and MCP."""
    if command == "whoami":
        token, creds = bearer_token()
        status, result = gateway_request("GET", "/api/workspaces")
        workspaces = result.get("workspaces") if isinstance(result, dict) else result
        return status, {
            "ok": True,
            "explorer_base": explorer_base(creds),
            "email": creds.get("email"),
            "token_preview": f"{token[:6]}…",
            "workspaces": workspaces,
        }

    if command == "list-workspaces":
        return gateway_request("GET", "/api/workspaces", auto_workspace=False)

    if command == "select-workspace":
        wid = str(kwargs["workspace_id"]).strip()
        return gateway_request(
            "POST",
            f"/api/workspaces/{urllib.parse.quote(wid)}/select",
            {},
            auto_workspace=False,
        )

    if command == "search-sessions":
        payload = {
            "from": kwargs["from_time"],
            "to": kwargs["to_time"],
            "limit": kwargs.get("limit", 50),
            "cursor": kwargs.get("cursor"),
            "agent_name": kwargs.get("agent_name"),
        }
        return gateway_request(
            "POST",
            lake_path("/v1/llm/sessions/search"),
            {k: v for k, v in payload.items() if v is not None},
        )

    if command == "get-session":
        path = lake_path(f"/v1/llm/sessions/{urllib.parse.quote(str(kwargs['session_id']))}")
        path += query_string({"limit": kwargs.get("limit", 200)})
        return gateway_request("GET", path)

    if command == "get-session-observations":
        path = lake_path(
            f"/v1/llm/sessions/{urllib.parse.quote(str(kwargs['session_id']))}/observations"
        )
        path += query_string(
            {"limit": kwargs.get("limit", 200), "cursor": kwargs.get("cursor")}
        )
        return gateway_request("GET", path)

    if command == "search-observations":
        types = kwargs.get("observation_types")
        if isinstance(types, str):
            types = [t.strip() for t in types.split(",") if t.strip()] or None
        payload = {
            "from": kwargs["from_time"],
            "to": kwargs["to_time"],
            "session_id": kwargs.get("session_id"),
            "observation_types": types,
            "limit": kwargs.get("limit"),
            "cursor": kwargs.get("cursor"),
        }
        return gateway_request(
            "POST",
            lake_path("/v1/llm/observations/search"),
            {k: v for k, v in payload.items() if v is not None},
        )

    if command == "get-observation":
        return gateway_request(
            "GET",
            lake_path(f"/v1/llm/observations/{urllib.parse.quote(str(kwargs['span_id']))}"),
        )

    if command == "get-trace":
        path = lake_path(f"/v1/llm/traces/{urllib.parse.quote(str(kwargs['trace_id']))}")
        path += query_string(
            {"limit": kwargs.get("limit", 200), "cursor": kwargs.get("cursor")}
        )
        return gateway_request("GET", path)

    if command == "logs-by-session":
        sid = sql_literal(str(kwargs["session_id"]))
        sql = (
            "SELECT timestamp, trace_id, span_id, severity_text, body "
            f"FROM union_logs WHERE session_id = {sid} ORDER BY timestamp"
        )
        return gateway_request("POST", lake_path("/v1/query/sql"), {"sql": sql})

    if command == "logs-by-trace":
        tid = sql_literal(str(kwargs["trace_id"]))
        sql = (
            "SELECT timestamp, span_id, severity_text, body "
            f"FROM union_logs WHERE trace_id = {tid} ORDER BY timestamp"
        )
        return gateway_request("POST", lake_path("/v1/query/sql"), {"sql": sql})

    raise RuntimeError(f"unknown command: {command}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("whoami", help="Check credentials without printing the token")
    commands.add_parser("list-workspaces")
    select = commands.add_parser("select-workspace")
    select.add_argument("workspace_id")

    search_sess = commands.add_parser("search-sessions")
    search_sess.add_argument("--from", dest="from_time", required=True)
    search_sess.add_argument("--to", dest="to_time", required=True)
    search_sess.add_argument("--limit", type=int, default=50)
    search_sess.add_argument("--cursor")
    search_sess.add_argument("--agent-name")

    get_sess = commands.add_parser("get-session")
    get_sess.add_argument("session_id")
    get_sess.add_argument("--limit", type=int, default=200)

    sess_obs = commands.add_parser("get-session-observations")
    sess_obs.add_argument("session_id")
    sess_obs.add_argument("--limit", type=int, default=200)
    sess_obs.add_argument("--cursor")

    search_obs = commands.add_parser("search-observations")
    search_obs.add_argument("--from", dest="from_time", required=True)
    search_obs.add_argument("--to", dest="to_time", required=True)
    search_obs.add_argument("--session-id")
    search_obs.add_argument("--observation-types", help="comma-separated")
    search_obs.add_argument("--limit", type=int)
    search_obs.add_argument("--cursor")

    get_obs = commands.add_parser("get-observation")
    get_obs.add_argument("span_id")

    get_trace = commands.add_parser("get-trace")
    get_trace.add_argument("trace_id")
    get_trace.add_argument("--limit", type=int, default=200)
    get_trace.add_argument("--cursor")

    logs = commands.add_parser("logs-by-session")
    logs.add_argument("session_id")

    logs_t = commands.add_parser("logs-by-trace")
    logs_t.add_argument("trace_id")

    args = parser.parse_args()
    kwargs = {k: v for k, v in vars(args).items() if k != "command" and v is not None}
    status, result = call(args.command, **kwargs)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, MissingCredentialsError) as error:
        print(f"softprobe_api: {error}", file=sys.stderr)
        sys.exit(1)
