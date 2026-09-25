# Implementation status

2026-09-25, runtime v0.1 (branch m1-working-runtime).

## Working and verified live on the workstation

- `aa` daemon (systemd user), SQLite state, CLI, ntfy push + reply buttons over Tailscale.
- Subscription workers: `codex exec` gpt-6-luna (live task t0925-b68ad, 13 s) and `claude -p`
  claude-opus-5-5 medium (live task t0925-1186d, 21 s), both with checks passing.
- Local decider: SemIf (Qwen3.5-4B, no-network container, Unix socket) as default, CLM and
  keyword rules selectable; benchmarked on 120 + 80 blind tasks (eval/RESULTS.md).
- Triage with owner pick on disagreement (exercised live), checks from `.agenticarch.toml`.
- `aa doctor`: both subscriptions, CLM, ntfy, private case-repo access all OK.

- Spec-check loop: Opus 5.5 judges acceptance criteria after checks; max 3 loops, then owner (D017).

## Implemented, tested offline, not yet exercised live

- Deep-case flow end to end (Pro draft, Opus x Astra rounds, GO/CLARIFY, owner questions,
  pause/resume, post-GO verification, local fixes, DESIGN_ISSUE back to Pro).
  Needs a first real case with a GitHub target repo.
- Autodetected checks confirmation, retries and lane escalation, scope enforcement.

## Not implemented

- Triage policy decision pending (Codex alone vs Codex + SemIf); see eval/RESULTS.md.
- Per-generation effort switching: dropped by the owner (D015).
- Skill installation on the Mac (skills are in `skills/`; installer ready).
