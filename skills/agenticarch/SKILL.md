---
name: agenticarch
description: "Hand a coding task to the AgenticArch coordinator (aa): tiered triage, subscription workers, checks, and GPT-6 Pro deep cases. Use when the owner says 'aa', 'agenticarch', 'queue this', or asks to delegate a task to the coordinator, or to check/answer an aa task or case."
---

# Delegate to the AgenticArch coordinator

The `aa` daemon on the workstation runs tasks end to end: Codex+CLM triage (the owner
decides on disagreement), a Luna/Astra/Opus worker in a git worktree, the repo's
required checks, retries/escalation, and for tough work a GPT-6 Pro deep case. The
owner is notified by ntfy. You only queue, inspect and relay; you do not do the work.

## Queue a task

1. Determine the target repository: the current project root unless the owner names
   another. It must be a git repo; the task starts from its current HEAD (uncommitted
   changes are NOT included — tell the owner and offer to commit first if relevant).
2. Restate the task as one self-contained paragraph with the concrete goal and
   acceptance criteria the owner gave. Do not invent requirements.
3. Run: `aa task --repo <repo> "<task>"`. Add `--tier routine|bounded|medium_tough|tough`
   only when the owner explicitly chose the tier (e.g. "make this a Pro case" -> tough).
4. Report the task id and that updates arrive by ntfy.

On a machine without `aa` (e.g. the Mac), run the same commands over Tailscale SSH:
`ssh rosh@rs-workstation-linux aa ...` with the workstation path of the repo (ask
the owner if the repo is not cloned there).

## Inspect and answer

- `aa status` (active) / `aa status -a` (all), `aa show <id>` (details + events).
- `aa prompt <case>` prints the one-line prompt to paste into the case's Pro chat.
- Owner answers (only relay what the owner actually said):
  `aa answer "tier <task> <tier>"`, `aa answer "checks <task> ok|none"`,
  `aa answer "answer <case> <text>"`, `aa answer "resume <case>"`,
  `aa answer "cancel <id>"`, `aa answer "retry <task>"`.
- `aa doctor` verifies subscriptions, CLM, ntfy and case-repo access.

## Boundaries

Never pass API keys or change auth; workers are subscription-only by design. Do not
merge or deploy what `aa` produced: it delivers branches (`aa/<task>` or
`aa/case-<case>`); merging is the owner's call.
