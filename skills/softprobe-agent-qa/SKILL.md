---
name: softprobe-agent-qa
description: Diagnose Softprobe Agent QA sessions and traces in Explorer. Use when investigating failed agent runs, tool errors, generations, sessions, or Explorer telemetry for Softprobe Agent QA.
when_to_use: Softprobe Agent QA, Explorer sessions, traces, generations, tool errors, softprobe-agent-qa, softprobe skills investigate
---

# Softprobe Agent QA (investigate)

Read-only investigation of Softprobe Agent QA Sessions and traces via the Explorer gateway.

Humans bootstrap access; coding agents must **not** run browser login.

## Bootstrap

1. If credentials are missing or expired, tell the human to run:

```bash
python3 skills/softprobe-agent-qa/scripts/login.py
# after npx skills install, scripts may live under ~/.agents/skills/softprobe-agent-qa/scripts/
```

2. Verify:

```bash
python3 skills/softprobe-agent-qa/scripts/softprobe_api.py whoami
```

3. If the API returns **409** / `workspace_picker_required`:

```bash
python3 skills/softprobe-agent-qa/scripts/softprobe_api.py list-workspaces
python3 skills/softprobe-agent-qa/scripts/softprobe_api.py select-workspace <workspace_id>
```

Or ask the human to pick a workspace in [Explorer](https://explorer.softprobe.ai).

Read [references/auth-and-routing.md](references/auth-and-routing.md) and [references/api-cheat-sheet.md](references/api-cheat-sheet.md).

## Investigate (narrowest first)

| Known | Command |
|---|---|
| `session_id` | `get-session` then `get-session-observations` |
| `trace_id` | `get-trace` |
| `span_id` | `get-observation` |
| Time window only | `search-sessions` or `search-observations` with `--from` / `--to` (UTC) |
| Need log context | `logs-by-session` or `logs-by-trace` (fixed templates only) |

Prefer narrow time windows. Follow `next_cursor` when paging.

Cite `session_id` / `trace_id` / `span_id` in conclusions. Link:

`https://explorer.softprobe.ai?session=<session_id>`

## Guardrails

- **Read-only.** Do not ingest OTLP, create scores, or run arbitrary SQL.
- Do not ask the human to paste JWTs into chat.
- Do not call `https://thelake.softprobe.ai` directly with a user token.
- Do not send `X-Softprobe-Assertion` (the gateway mints it).
- This skill is **not** the OpenCode capture plugin (`@softprobe/opencode-plugin`).
