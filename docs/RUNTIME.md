# Runtime: the `aa` coordinator

Operations manual for the working system (installed on the workstation 2026-09-25).

## Components

| Unit (systemd --user) | What | Where |
| --- | --- | --- |
| `aa-daemon` | Coordinator: tasks, deep cases, owner replies | `bin/aa daemon`, state in `~/.local/share/agenticarch/aa.sqlite` |
| `aa-semif` | SemIf decider: Qwen3.5-4B in the `ai-lab/private-semif` container, `--network none`, Unix socket, ~9 GB VRAM | model + source in `~/.local/share/agenticarch/semif/` |
| `aa-clm-embed`, `aa-clm` | CLM (vLLM Qwen3-8B + clm-serve), loopback; **disabled** since D016, re-enable with `decider.backend = "clm"` | venv `~/.local/share/agenticarch/clm-venv` |
| `aa-ntfy-forward` | Exposes loopback ntfy on the Tailscale IP :8093 | `deploy/bin/tcp_forward.py` |
| docker `ntfy` | Self-hosted ntfy (rootless Docker, 127.0.0.1:8093) | data in `~/.local/share/agenticarch/ntfy` |

Workers are the owner's subscription CLIs: `~/.local/bin/codex` (ChatGPT login) and
`~/.local/bin/claude` (Claude Max login). `aa doctor` verifies all of it.

## Task flow

```text
aa task "..."  (or the agenticarch skill in Codex desktop)
  -> triage: Codex gpt-6-luna high (read-only, JSON) + SemIf tier vote
       agree / one abstains -> tier;  disagree -> ntfy asks owner (buttons)
  -> checks: .agenticarch.toml [checks] or autodetect + one-time owner OK
  -> routine: luna_low | bounded: luna_high | medium_tough: decider picks the model (astra_high | opus_high)
     tough (or Pro category): deep case
  -> worker in git worktree aa/<task> -> snapshot -> coordinator runs checks
     fail -> failure triage per failed check:
       passes on rerun: FLAKY (noted) | SemIf says environment: pause + ntfy Retry/Treat as code/Cancel
       same failure on the base commit: PRE_EXISTING (spec judge told) | else CODE:
       retry same lane with the failure (2x), then escalate lane, then deep case
  -> pass: spec check — Opus 5.5 medium judges every acceptance criterion (+ test tampering)
     against the diff, read-only in the worktree
       unmet -> back to the same worker with the reasons; worker fixes or answers REBUTTAL:
       after 3 loops -> ntfy: Accept / One more / Cancel
  -> met: squash to one commit, push branch, ntfy "Done"
```

The coordinator, never a model, commits, runs checks and decides pass/fail. Claude
workers run in auto mode with hard denies (no push, no remotes, no sudo/ssh, credential
files unreadable, no MCP connectors); Codex workers in Codex's workspace-write sandbox.
Workers never get API keys (scrubbed env + auth-mode check before every dispatch); Claude's
`modelUsage` must show the requested model or the job fails.

## Deep case flow

```text
case/<id> branch in private stardustx8/GPT-Pro-Escalation, BRIEF.md + PRO-TURN-01.md
  -> ntfy: "Start a NEW Pro chat 'AA <id>', paste: <one line>"
  -> Pro (GitHub connector) writes SOLUTION.md, OBJECTIONS.md, turns/pro-01.md
  -> daemon polls the branch (60 s) -> Opus 5.5 high x Astra high challenge rounds
     (each co-edits cases/<id>/ only; up to 5 rounds; both AGREE ends early)
  -> ntfy: "Continue in the SAME chat, paste: <one line>" -> Pro review
       GO: Pro implements on aa/case-<id> in the target repo -> daemon runs checks
           pass -> Done; small failures -> Opus high fixes (2x); DESIGN_ISSUE -> Pro again
       CLARIFY: owner questions -> ntfy -> `aa answer "answer <id> ..."`; else next cycle
       2 reviews without GO -> PAUSED (resume or answer)
```

The target's base commit is pushed as `aa/base-<case>` so Pro reads exactly what the
workers saw. Challengers read the target at that commit in a detached worktree; any
edit outside `cases/<id>/` or to the target snapshot is reverted and logged.

## Owner interaction

- Phone: ntfy app, server `http://100.114.173.57:8093`, topic `agenticarch`. Buttons
  post replies to `agenticarch-replies`; the daemon reads them.
- Workstation: `aa status`, `aa show <id>`, `aa prompt <case>`, `aa answer "<reply>"`.
- Reply grammar: `tier <task> <tier>`, `checks <task> ok|none`, `answer <case> <text>`,
  `resume <case>`, `cancel <id>`, `retry <task>` (also: one more spec loop / re-run checks after
  an environment fix), `accept <task>` (deliver although the spec reviewer still objects),
  `code <task>` (treat an environment verdict as a code failure).

## Local decider: what it decides and how well

The decider (`decider.backend`: semif default, clm, rules) votes on the tier, picks the
medium-tough model, and ranks files for the case BRIEF. Every call is logged in the
`decisions` table with the final choice and later outcome; owner picks become labels.
Wordings live in `aa/decisions.py` and are chosen by `tools/eval_decisions.py`.

Benchmark (eval/RESULTS.md), tier accuracy on a blind holdout: Codex triage 90%, SemIf
82%, keyword rules 57%, CLM 38%. Votes below `decider.min_confidence` (0.2) abstain.
As a second voter next to Codex, no decider lowered total error cost; ask-on-disagreement
pings the owner on ~20% of tasks with SemIf.

## Operations

```sh
aa doctor                                   # health of everything
systemctl --user status aa-daemon aa-semif aa-ntfy-forward
journalctl --user -u aa-daemon -f
ls ~/.local/share/agenticarch/logs          # one log per model job (full CLI output)
sqlite3 ~/.local/share/agenticarch/aa.sqlite 'select * from events order by id desc limit 20'
```

Restarting the daemon is safe: busy flags are cleared and every task/case resumes from
its stored state. Worktrees live in `~/.local/share/agenticarch/worktrees`; finished
tasks remove theirs, branches stay in the target repo.

Units start with the login session. For start at boot without login run once:
`sudo loginctl enable-linger rosh`.

## Not yet done

- Decide the triage policy (Codex alone vs Codex + SemIf; eval/RESULTS.md).
- Re-run the benchmark on the owner's real tasks once enough are logged.
- Mac: skills call `aa` via Tailscale SSH; the target repo must exist on the workstation.
