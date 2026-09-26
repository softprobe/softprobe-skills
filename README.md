# Softprobe Skills

Apache-2.0 skills and Claude Code plugin for **Softprobe Agent QA**: ask your coding agent to investigate Sessions and traces in [Explorer](https://explorer.softprobe.ai).

This is **not** the OpenCode capture package (`@softprobe/opencode-plugin`). Capture installs from Explorer; this repo is for **read-only diagnose**.

## Two steps (hosted MCP)

### 1. Add Softprobe MCP

**Claude Code**

```bash
claude mcp add --transport http softprobe https://explorer.softprobe.ai/mcp
```

**Cursor**

Settings → MCP → Add server (URL / HTTP):

`https://explorer.softprobe.ai/mcp`

Or:

```bash
cursor --add-mcp '{"name":"softprobe","url":"https://explorer.softprobe.ai/mcp"}'
```

### 2. Ask your coding agent

> Use Softprobe: why did session `sess_…` fail? Check tool errors and the last generation.

The first tool call opens a browser to sign in to Softprobe (OAuth). After you Allow, the agent can use `get_session`, `search_sessions`, and the other read-only tools.

Docs: [Investigate with a coding agent](https://docs.softprobe.ai/en/agent-qa/coding-agent-skills)

## Optional: skill package

Install the skill text (investigation playbook) beside MCP:

```bash
npx skills add softprobe/softprobe-skills -g -y \
  -a cursor -a claude-code -a codex -a opencode \
  -s softprobe-agent-qa
```

## Fallback: local stdio MCP

If you cannot use hosted MCP (air-gapped / custom Explorer):

```bash
npx skills add softprobe/softprobe-skills -g -y \
  -a cursor -a claude-code -a codex -a opencode \
  -s softprobe-agent-qa
bash ~/.agents/skills/softprobe-agent-qa/scripts/install-mcp.sh
python3 ~/.agents/skills/softprobe-agent-qa/scripts/login.py
```

## Layout (DRY)

```text
skills/softprobe-agent-qa/     # skill playbook + local stdio fallback
.claude-plugin/plugin.json
install.sh
```

## License

Apache License 2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

## Operator note (Explorer)

Hosted MCP lives on Explorer: `POST /mcp`, OAuth at `/oauth/*`, discovery under `/.well-known/`. Supabase Auth redirect allowlist must include:

- `https://explorer.softprobe.ai/auth/cli**`
- `https://explorer.softprobe.ai/oauth/authorize**`
