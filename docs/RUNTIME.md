# Runtime: the `aa` coordinator

Operations manual for the working system (installed on the workstation 2026-09-25).

## Components

| Unit (systemd --user) | What | Where |
| --- | --- | --- |
| `aa-daemon` | Coordinator: tasks, deep cases, owner replies | `bin/aa daemon`, state in `~/.local/share/agenticarch/aa.sqlite` |
| `aa-clm-embed` | CLM encoder: vLLM Qwen3-8B pooling, loopback :8090, ~24 GB VRAM | venv `~/.local/share/agenticarch/clm-venv` |
| `aa-clm` | CLM System One API (`clm-serve`), loopback :8700, head `~/.cache/clm/CLM_v0.1-8B.pt` | same venv |
| `aa-ntfy-forward` | Exposes loopback ntfy on the Tailscale IP :8093 | `deploy/bin/tcp_forward.py` |
| docker `ntfy` | Self-hosted ntfy (rootless Docker, 127.0.0.1:8093) | data in `~/.local/share/agenticarch/ntfy` |

Workers are the owner's subscription CLIs: `~/.local/bin/codex` (ChatGPT login) and
`~/.local/bin/claude` (Claude Max login). `aa doctor` verifies all of it.

## Task flow

```text
aa task "..."  (or the agenticarch skill in Codex desktop)
  -> triage: Codex gpt-6-luna high (read-only, JSON) + CLM tier vote
       agree / one abstains -> tier;  disagree -> ntfy asks owner (buttons)
  -> checks: .agenticarch.toml [checks] or autodetect + one-time owner OK
  -> routine: luna_low | bounded: luna_high | medium_tough: CLM picks astra_high/opus_medium/opus_high
     tough (or Pro category): deep case
  -> worker in git worktree aa/<task> -> snapshot -> coordinator runs checks
  -> pass: squash to one commit, push branch, ntfy "Done"
     fail: retry same lane with the failure (2x), then escalate lane, then deep case
```

The coordinator, never a model, commits, runs checks and decides pass/fail. Workers
never get API keys (scrubbed env + auth-mode check before every dispatch); Claude's
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
  `resume <case>`, `cancel <id>`, `retry <task>`.

## CLM: what it decides and how well

CLM votes on the tier, picks the medium-tough peer, and ranks files for the case
BRIEF. Every call is logged in the `decisions` table with the final choice and later
outcome, i.e. owner picks on disagreement become labels for fine-tuning.

Zero-shot quality is limited. Measured 2026-09-25 on 8 hand-labelled tasks: option
wording "short concrete answers" 5/8, tier names 2/8, seniority phrasing 2/8; it tends
to collapse onto one class and missed both tough examples. Hence `clm.min_confidence`
(0.2): below it a vote is an abstention, not a disagreement. Peer choice is close to
uniform zero-shot (so the default `astra_high` usually wins). Plan: fine-tune the head on
the logged decisions once ~100 labelled tasks exist (`contrastive-lm` fine-tuning).

## Operations

```sh
aa doctor                                   # health of everything
systemctl --user status aa-daemon aa-clm aa-clm-embed aa-ntfy-forward
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

- Per-generation effort switching (Codex fork with an Astra-Ares-style checkpoint for
  worker `codex exec`). Today effort is fixed per job by lane.
- CLM fine-tuning on logged decisions.
- Mac: skills call `aa` via Tailscale SSH; the target repo must exist on the workstation.
