---
name: softprobe-agent-qa
description: Diagnose Softprobe Agent QA sessions and traces in Explorer. Prefer Softprobe hosted MCP at https://explorer.softprobe.ai/mcp. Use when investigating failed agent runs, tool errors, generations, sessions, or Explorer telemetry.
when_to_use: Softprobe Agent QA, Explorer sessions, traces, generations, tool errors, softprobe-agent-qa, softprobe MCP
---

# Softprobe Agent QA (investigate)

Read-only investigation of Softprobe Agent QA Sessions and traces.

## Prefer hosted MCP

Endpoint: `https://explorer.softprobe.ai/mcp`

If tools are missing, tell the human to add that URL once:

```bash
claude mcp add --transport http softprobe https://explorer.softprobe.ai/mcp
```

Auth is browser OAuth on first use (human signs in and clicks Allow). Do **not** ask them to paste JWTs.

## Tools

| Known | Tool |
|---|---|
| `session_id` | `get_session` then `get_session_observations` |
| `trace_id` | `get_trace` |
| `span_id` | `get_observation` |
| Time window | `search_sessions` / `search_observations` (`from_time` / `to_time` UTC) |
| Logs | `logs_by_session` / `logs_by_trace` |

Cite ids and link `https://explorer.softprobe.ai?session=<session_id>`.

## Guardrails

- **Read-only.** No OTLP ingest, scores, or arbitrary SQL.
- Do not call `https://thelake.softprobe.ai` with a user token.
- Do not send `X-Softprobe-Assertion`.
- Not the OpenCode capture plugin.

## Local fallback

Only if hosted MCP is unavailable: skill scripts under `scripts/` (`login.py`, `softprobe_api.py`, `install-mcp.sh`). See [references/api-cheat-sheet.md](references/api-cheat-sheet.md).
