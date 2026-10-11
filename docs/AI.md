# Using scriber from an AI agent

scriber is built to be driven by an agent as well as by a human. The agent-facing instructions live in
[AGENTS.md](../AGENTS.md) (the cross-agent convention) and are mirrored by a thin skill at
`.claude/skills/scriber/SKILL.md`.

## Contract

| Need | Command | Output |
|---|---|---|
| Is the machine ready? | `scriber doctor --json` | `{"ok": bool, "checks": [...]}`, exit 3 if blocking |
| What can I configure? | `scriber describe` | JSON: commands, every setting with env var, CLI flag, default |
| What would happen? | `scriber run <src> --dry-run --json` | Planned jobs and exact output paths, no models loaded |
| Do it | `scriber run <src> --json` | Manifest on stdout, logs on stderr |

Exit codes: `0` ok, `2` usage or invalid settings, `3` environment, `4` some files failed.

Secrets never appear in `describe`, `doctor` or `--json` output.

## Typical agent flow

1. `scriber doctor --json`. Fix blocking checks (usually ffmpeg), mention a missing token (no speaker labels).
2. Ask the user the questions listed in AGENTS.md.
3. `scriber run ... --dry-run --json`, show the plan, confirm if it is a folder or many files.
4. `scriber run ... --json`, then report outputs, failures and warnings from the manifest.
