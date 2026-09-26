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

    if args.command == "whoami":
        token, creds = bearer_token()
        status, result = gateway_request("GET", "/api/workspaces")
        result = {
            "ok": True,
            "explorer_base": explorer_base(creds),
            "email": creds.get("email"),
            "token_preview": f"{token[:6]}…",
            "workspaces": result.get("workspaces") if isinstance(result, dict) else result,
        }
    elif args.command == "list-workspaces":
        status, result = gateway_request("GET", "/api/workspaces", auto_workspace=False)
    elif args.command == "select-workspace":
        wid = args.workspace_id.strip()
        status, result = gateway_request(
            "POST",
            f"/api/workspaces/{urllib.parse.quote(wid)}/select",
            {},
            auto_workspace=False,
        )
    elif args.command == "search-sessions":
        payload = {
            "from": args.from_time,
            "to": args.to_time,
            "limit": args.limit,
            "cursor": args.cursor,
            "agent_name": args.agent_name,
        }
        status, result = gateway_request(
            "POST",
            lake_path("/v1/llm/sessions/search"),
            {k: v for k, v in payload.items() if v is not None},
        )
    elif args.command == "get-session":
        path = lake_path(f"/v1/llm/sessions/{urllib.parse.quote(args.session_id)}")
        path += query_string({"limit": args.limit})
        status, result = gateway_request("GET", path)
    elif args.command == "get-session-observations":
        path = lake_path(
            f"/v1/llm/sessions/{urllib.parse.quote(args.session_id)}/observations"
        )
        path += query_string({"limit": args.limit, "cursor": args.cursor})
        status, result = gateway_request("GET", path)
    elif args.command == "search-observations":
        payload = {
            "from": args.from_time,
            "to": args.to_time,
            "session_id": args.session_id,
            "observation_types": (
                args.observation_types.split(",") if args.observation_types else None
            ),
            "limit": args.limit,
            "cursor": args.cursor,
        }
        status, result = gateway_request(
            "POST",
            lake_path("/v1/llm/observations/search"),
            {k: v for k, v in payload.items() if v is not None},
        )
    elif args.command == "get-observation":
        status, result = gateway_request(
            "GET",
            lake_path(f"/v1/llm/observations/{urllib.parse.quote(args.span_id)}"),
        )
    elif args.command == "get-trace":
        path = lake_path(f"/v1/llm/traces/{urllib.parse.quote(args.trace_id)}")
        path += query_string({"limit": args.limit, "cursor": args.cursor})
        status, result = gateway_request("GET", path)
    elif args.command == "logs-by-session":
        sid = sql_literal(args.session_id)
        sql = (
            "SELECT timestamp, trace_id, span_id, severity_text, body "
            f"FROM union_logs WHERE session_id = {sid} ORDER BY timestamp"
        )
        status, result = gateway_request(
            "POST", lake_path("/v1/query/sql"), {"sql": sql}
        )
    elif args.command == "logs-by-trace":
        tid = sql_literal(args.trace_id)
        sql = (
            "SELECT timestamp, span_id, severity_text, body "
            f"FROM union_logs WHERE trace_id = {tid} ORDER BY timestamp"
        )
        status, result = gateway_request(
            "POST", lake_path("/v1/query/sql"), {"sql": sql}
        )
    else:
        raise RuntimeError(f"unknown command: {args.command}")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, MissingCredentialsError) as error:
        print(f"softprobe_api: {error}", file=sys.stderr)
        sys.exit(1)
