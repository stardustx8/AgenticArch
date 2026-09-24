# Implementation status

Date: 2026-09-24

## Delivered in this kit

- Self-contained architecture, routing/verification policy, Pro/Fable protocol and state machine.
- Phased implementation plan, security/recovery guidance and acceptance matrix.
- Main coding-agent implementation prompt and participant/return prompts for real review cases.
- Versioned policy and local configuration example, JSON schemas and synthetic fixtures.
- Generic review-repository and case templates.
- Dependency-free pure reference kernel with offline unit tests and kit consistency checks.
- Directly revised skills with complete references and a dry-run-first, backup-preserving installer.
- Owner requirements, workstation-first extensions and an explicit Pro UI capability gate.
- Primary-source semantic-decision research, prioritized use cases, operator catalog, evaluation plan and offline decision-plane helpers/tests.

## Not delivered or verified

The two actual skill definitions are directly revised under `skills/prepare-sol-pro-architecture-review/` and `skills/fable-adversarial-review/`, preserving their exact identifiers and supplying complete references. The installed local helper trees were not supplied; preserving those extra files is an installation requirement, not a completed observation. No skill-upgrade prompts are included.

Automatic Pro web submission is **not qualified**: the current standard Computer Use documentation excludes automating ChatGPT itself. The shipped default is manual Pro web transfer, with a conditional capability-gated future UI transport. See `docs/COMPUTER-USE-GATE.md`. This is not a verified unattended system.

Live Codex dispatch, the owner's installed SemIf backend, Computer Use upload/continuation, Fable invocation, Git collaboration, persistent runtime state, safe context export, skill installation and full end-to-end operation have **not** been executed or validated by this kit. They are implementation and local qualification work, not hidden completed features.

The reference functions validate supplied observations. They cannot authenticate a participant or execute a test by themselves. Production adapters must collect trusted observations, recompute manifests, enforce path/export policies and preserve state atomically.

## External delivery

GitHub development context is organized through `START-HERE.md`, `docs/SESSION-HANDOFF.md` and `docs/DECISIONS.md`. Source and documentation are published as ordinary repository files, not only downloadable archives. Use the actual current remote revision for future sessions.

A local archive or local Git commit does not establish a remote push. Verify the actual remote `main` commit and file contents after publishing. Review-repository creation is a separate authorized operation, not implied by this kit's templates.

## Starting point

Read `prompts/IMPLEMENT-AGENTICARCH.md`. Run:

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_kit.py
```

Mark live acceptance scenarios `NOT_RUN` until exercised in the real environment. Do not relabel offline successes as production readiness.
