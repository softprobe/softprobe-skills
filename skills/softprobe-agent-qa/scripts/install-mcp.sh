#!/usr/bin/env bash
# Register Softprobe Agent QA MCP with Cursor and/or Claude Code (few steps).
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
SERVER="$SCRIPTS/mcp_server.py"
NAME="softprobe"

if [[ ! -f "$SERVER" ]]; then
  echo "Missing $SERVER" >&2
  exit 1
fi

MCP_JSON=$(python3 -c "
import json
print(json.dumps({
  'name': '$NAME',
  'type': 'stdio',
  'command': 'python3',
  'args': ['$SERVER'],
}))
")

added=0

if command -v cursor >/dev/null 2>&1; then
  cursor --add-mcp "$MCP_JSON"
  echo "Cursor: added MCP server '$NAME'"
  added=1
else
  echo "Cursor CLI not found — skip. Manual:"
  echo "  cursor --add-mcp '$MCP_JSON'"
fi

if command -v claude >/dev/null 2>&1; then
  # Remove prior registration so re-run is idempotent
  claude mcp remove -s user "$NAME" >/dev/null 2>&1 || true
  claude mcp add -s user "$NAME" -- python3 "$SERVER"
  echo "Claude Code: added MCP server '$NAME' (user scope)"
  added=1
else
  echo "Claude CLI not found — skip. Manual:"
  echo "  claude mcp add -s user $NAME -- python3 $SERVER"
fi

if [[ "$added" -eq 0 ]]; then
  echo "No supported agent CLI found." >&2
  exit 1
fi

echo
echo "Next (human only, once): python3 $SCRIPTS/login.py"
echo "Then ask your agent to use Softprobe Agent QA / softprobe MCP tools."
