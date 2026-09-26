# Contributing

Thanks for helping improve Softprobe skills.

## Rules

1. **One skill tree.** Put content only under `skills/<name>/`. Do not create per-agent copies of `SKILL.md` or scripts.
2. **Symlink install.** `install.sh` and `npx skills` must symlink by default. `--copy` is an escape hatch only.
3. **No secrets.** Never commit tokens, `.env`, or `~/.softprobe` material. Do not ask users to paste JWTs into issues or chat.
4. **Read-only Agent QA skill.** Do not add ingest, score writes, or arbitrary SQL to `softprobe-agent-qa`.
5. **Apache-2.0.** Contributions are under the same license as the repository.

## Develop

```bash
python3 -m unittest discover -s tests -v
./install.sh   # symlink into local agent skill dirs
```

Claude Code:

```bash
claude --plugin-dir .
```

## Pull requests

- Keep changes small and focused.
- Update `skills/*/SKILL.md` or `references/` when behavior changes.
- Add or update unit tests for script changes.
- Do not edit private Softprobe monorepo files in this repo.
