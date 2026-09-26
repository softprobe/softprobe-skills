#!/usr/bin/env bash
# Symlink Softprobe skills into agent discovery paths (DRY — never copy by default).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$ROOT/skills/softprobe-agent-qa"
SKILL_NAME="softprobe-agent-qa"
COPY=0

usage() {
  cat <<EOF
Usage: ./install.sh [--copy] [--help]

Symlink (default) $SKILL_NAME into:
  ~/.agents/skills/$SKILL_NAME   (Cursor, Codex, OpenCode, peers)
  ~/.claude/skills/$SKILL_NAME   (Claude Code skill discovery)
  ~/.cursor/skills/$SKILL_NAME   (Cursor user skills, if used)
  ~/.codex/skills/$SKILL_NAME    (Codex CLI)
  ~/.config/opencode/skills/$SKILL_NAME

Claude plugin (same clone, no extra copy):
  claude --plugin-dir $ROOT

Preferred cross-agent install:
  npx skills add softprobe/softprobe-skills -g

--copy   Copy instead of symlink (escape hatch only)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy) COPY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ ! -f "$SKILL_SRC/SKILL.md" ]]; then
  echo "Missing $SKILL_SRC/SKILL.md" >&2
  exit 1
fi

link_or_copy() {
  local dest_dir="$1"
  mkdir -p "$dest_dir"
  local dest="$dest_dir/$SKILL_NAME"
  if [[ -L "$dest" || -e "$dest" ]]; then
    rm -rf "$dest"
  fi
  if [[ "$COPY" -eq 1 ]]; then
    cp -R "$SKILL_SRC" "$dest"
    echo "copied -> $dest"
  else
    ln -s "$SKILL_SRC" "$dest"
    echo "symlink -> $dest"
  fi
}

link_or_copy "${HOME}/.agents/skills"
link_or_copy "${HOME}/.claude/skills"
link_or_copy "${HOME}/.cursor/skills"
link_or_copy "${HOME}/.codex/skills"
link_or_copy "${HOME}/.config/opencode/skills"

echo
echo "Next:  bash $SKILL_SRC/scripts/install-mcp.sh   # cursor --add-mcp / claude mcp add"
echo "Then:  python3 $SKILL_SRC/scripts/login.py      # human only"
echo "Claude plugin: claude --plugin-dir $ROOT"
