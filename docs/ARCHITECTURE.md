# Architecture

Version 3, 2026-09-25. Implemented in `aa/`; operations in [RUNTIME](RUNTIME.md).

## Shape

One deterministic coordinator daemon owns all state (SQLite), all git operations and all
check runs. Models only produce text and file edits inside a worktree or a case
directory. The local CLM gives votes and rankings; it never authorizes anything.

```text
owner (Codex desktop skill / aa CLI / ntfy buttons)
            |
        aa daemon ── SQLite (tasks, cases, events, decisions, inbox)
       /    |     \
  CLM     workers   git: target repos (worktrees, aa/* branches)
 (local)  codex exec (Luna, Astra)      case repo GPT-Pro-Escalation (case/<id>)
          claude -p  (Opus 5.5)                   ^
                                                  | GitHub connector
                                          GPT-6 Pro in ChatGPT web
```

## Roles

| Tier | Worker |
| --- | --- |
| routine | GPT-6 Luna low |
| bounded | GPT-6 Luna high |
| medium_tough | GPT-6 Astra high, Claude Opus 5.5 medium or high (CLM picks, Astra default) |
| tough, or any Pro category | Deep case: GPT-6 Pro drafts, Opus 5.5 high and Astra high challenge, Pro decides GO and implements |

Fable 5.5 will replace Opus as the Claude challenger once released and qualified
(config `deep.challengers`). Fable 5.1 is not used.

## Invariants

- Subscription-only: API-key variables are scrubbed from every worker, auth mode is
  verified before dispatch, Claude's reported model must match the requested one.
- Completion = the coordinator's own check run on the committed snapshot passes.
  A model's "done", a debate consensus or a GO is never completion by itself.
- Write scope: workers write only their worktree; challengers only `cases/<id>/`;
  Pro only the case branch and, after GO, `aa/case-<id>` in the target repo.
- Delivery is a branch. Merging, deploying and publishing stay with the owner.
- Crash safety: every step is idempotent over stored state; restart resumes.
- Private data: cases live in the private case repo, never in this public repo.

## Code map

`aa/config.py` defaults + `~/.config/agenticarch/aa.toml`; `aa/db.py` schema;
`aa/tasks.py` triage/routing/work/verify; `aa/cases.py` deep flow; `aa/workers.py`
CLI execution and billing guard; `aa/clm.py` CLM decisions (uses `reference/clm.py`
validation); `aa/checks.py`; `aa/notify.py`; `aa/daemon.py`; `aa/cli.py`;
`aa/prompts/*.md` every model-facing text.

`reference/` holds the earlier contract validators (policy, effort leases, quota
attribution, decision-plane operators). They are tested and reusable but describe the
pre-runtime design where it differs (e.g. Pro<->Claude convergence); the runtime and
[owner requirements](OWNER-REQUIREMENTS.md) win on conflict.
