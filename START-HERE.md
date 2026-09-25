# Resume AgenticArch

`main` is the shared integration baseline. Start from the actual remote revision, not an older ZIP or a remembered chat. Read `AGENTS.md`, `docs/SESSION-HANDOFF.md`, `docs/OWNER-REQUIREMENTS.md`, `IMPLEMENTATION-STATUS.md` and `config/model-routing.json`, then the files relevant to the task.

Inspect the local worktree and remote head before editing. Preserve existing work. Use separate worktrees/branches for simultaneous edits and ordinary integration commits; never force-push to erase another session. Both harness variants are maintained together under `harnesses/`.

The initial workstation task is private, read-only capability discovery. Then follow [the implementation entry point](prompts/IMPLEMENT-AGENTICARCH.md). Run offline tests before and after changes. A passing mock does not establish a working provider or actual quota savings.

At closeout, update the handoff, implementation status and durable decisions. Record exact commands/results, live versus fixture evidence, remaining gates and next action. Read back the published commit. Never publish credentials, private model sessions, real review bundles or unrelated customer context.
