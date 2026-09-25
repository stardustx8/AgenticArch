# Implementation status

2026-09-25, runtime v0.1 (branch m1-working-runtime).

## Working and verified live on the workstation

- `aa` daemon (systemd user), SQLite state, CLI, ntfy push + reply buttons over Tailscale.
- Subscription workers: `codex exec` gpt-6-luna (live task t0925-b68ad, 13 s) and `claude -p`
  claude-opus-5-5 medium (live task t0925-1186d, 21 s), both with checks passing.
- Local CLM: vLLM Qwen3-8B encoder + clm-serve; tier votes, peer choice, context ranking
  with exact-token preflight and deployment digest; decisions logged.
- Triage with owner pick on disagreement (exercised live), checks from `.agenticarch.toml`.
- `aa doctor`: both subscriptions, CLM, ntfy, private case-repo access all OK.

## Implemented, tested offline, not yet exercised live

- Deep-case flow end to end (Pro draft, Opus x Astra rounds, GO/CLARIFY, owner questions,
  pause/resume, post-GO verification, local fixes, DESIGN_ISSUE back to Pro).
  Needs a first real case with a GitHub target repo.
- Autodetected checks confirmation, retries and lane escalation, scope enforcement.

## Not implemented

- Codex fork with per-generation effort checkpoint (effort is fixed per job today).
- CLM fine-tuning on logged decisions (zero-shot accuracy is limited; see RUNTIME).
- Skill installation on the Mac (skills are in `skills/`; installer ready).
