# AgenticArch agent instructions

Read START-HERE.md, docs/SESSION-HANDOFF.md, docs/OWNER-REQUIREMENTS.md and docs/RUNTIME.md first.

- The runtime is `aa/` (stdlib Python 3.11+). Keep it dependency-free; model-facing text lives in `aa/prompts/`.
- Subscription-only: never add API-key paths, paid fallbacks, or code that moves Claude credentials into another harness.
- The coordinator (not a model) commits, runs checks and decides completion. Keep write scopes: worktree for workers, `cases/<id>/` for challengers.
- CLM votes/ranks only; log every decision; never let it lower a floor or approve work.
- Every behaviour change needs a test in `tests/test_aa_runtime.py` (fake workers, real git).
- Deep-case content stays in the private repo stardustx8/GPT-Pro-Escalation.
- Work on branches with a PR per milestone; no force-push; update the handoff at closeout.
