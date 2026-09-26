# Auth and routing

## Credential

Explorer **user session** (same identity as the Softprobe Explorer browser app).

- Stored at `~/.softprobe/explorer/credentials.json` (mode `0600`)
- Or `SOFTPROBE_EXPLORER_TOKEN` for ephemeral use
- Created only by `scripts/login.py` (human runs browser login)

## HTTP routing

All lake reads go through the Explorer gateway:

```text
Authorization: Bearer <access_token>
https://explorer.softprobe.ai/api/thelake/v1/llm/...
```

Workspace APIs:

```text
GET  /api/workspaces
POST /api/workspaces/{id}/select
```

Override origin with `SOFTPROBE_EXPLORER_BASE` (local/dev only).

## Workspace selection

If the user belongs to multiple workspaces and none is selected, the gateway returns **HTTP 409** with `code: workspace_picker_required`. List workspaces, then `select-workspace`, or ask the human to select in Explorer.

## Never

- Paste access tokens into agent chat
- Call hosted `thelake.softprobe.ai` with a user JWT
- Send `X-Softprobe-Assertion` from the skill (gateway strips spoofed identity headers)
