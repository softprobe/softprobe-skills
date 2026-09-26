# API cheat sheet

Scripts live next to this skill: `scripts/softprobe_api.py`.

```bash
API="python3 skills/softprobe-agent-qa/scripts/softprobe_api.py"
# or after global install:
API="python3 $HOME/.agents/skills/softprobe-agent-qa/scripts/softprobe_api.py"
```

## Auth / workspace

```bash
$API whoami
$API list-workspaces
$API select-workspace <workspace_uuid>
```

## Sessions

```bash
$API search-sessions --from 2026-01-01T00:00:00Z --to 2026-01-08T00:00:00Z --limit 50
$API get-session <session_id>
$API get-session-observations <session_id> --limit 200
```

## Observations / traces

```bash
$API search-observations --from ... --to ... --session-id <id> --observation-types agent,generation,tool
$API get-observation <span_id>
$API get-trace <trace_id> --limit 200
```

Observation types: `span`, `event`, `generation`, `agent`, `tool`, `chain`, `retriever`, `evaluator`, `embedding`, `guardrail`.

## Correlated logs (fixed templates only)

```bash
$API logs-by-session <session_id>
$API logs-by-trace <trace_id>
```

## Explorer UI

`https://explorer.softprobe.ai?session=<session_id>`
