# Softprobe Skills

Apache-2.0 skills and Claude Code plugin for **Softprobe Agent QA**: ask your coding agent to investigate Sessions and traces in [Explorer](https://explorer.softprobe.ai).

This is **not** the OpenCode capture package (`@softprobe/opencode-plugin`). Capture installs from Explorer; this repo is for **read-only diagnose**.

## Three steps

### 1. Install

```bash
npx skills add softprobe/softprobe-skills -g
```

Works with Cursor, Claude Code, Codex, OpenCode, and peers (symlink by default).

Claude plugin (same repo, no second package):

```bash
git clone https://github.com/softprobe/softprobe-skills.git
claude --plugin-dir ./softprobe-skills
```

Fallback installer (symlink only unless `--copy`):

```bash
./install.sh
```

### 2. Sign in (human only)

Agents must not run login. You run:

```bash
python3 ~/.agents/skills/softprobe-agent-qa/scripts/login.py
```

Browser opens Explorer; credentials are saved under `~/.softprobe/explorer/` (mode `0600`).

### 3. Ask your coding agent

> Use Softprobe Agent QA: why did session `sess_…` fail? Check tool errors and the last generation.

Docs: [Investigate with a coding agent](https://docs.softprobe.ai/en/agent-qa/coding-agent-skills)

## Layout (DRY)

```text
skills/softprobe-agent-qa/     # single source of truth
.claude-plugin/plugin.json     # Claude Code plugin over the same skills/
install.sh                     # symlink into agent skill dirs
```

Do not fork `SKILL.md` per agent.

## License

Apache License 2.0 — see [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

## Operator note (Explorer)

`login.py` opens `/auth/cli?port=…` on Explorer. Production Explorer must serve that route, and Supabase Auth redirect allowlist must include `https://explorer.softprobe.ai/auth/cli**`.
