# Durable decision log

Initial record: 2026-09-24. Owner requirements are normative in [OWNER-REQUIREMENTS.md](OWNER-REQUIREMENTS.md). Entries below distinguish explicit owner choices from selected engineering decisions. Amendments need evidence, affected requirements, verification and a recorded decision; do not silently rewrite history.

## D001: GitHub as the shared project baseline

**Owner requirement.** Maintain the complete reusable solution and future development context in `stardustx8/AgenticArch`, integrated on `main`. Source, specifications, requirements, skills and test guidance belong together. Fresh sessions start from [START-HERE.md](../START-HERE.md) and the current handoff, not from chat memory. Preserve concurrent changes, use ordinary commits and never force-push to reconcile another session's work.

## D002: Fixed primary model roles

**Owner requirement.** Luna low/high for appropriate bounded work; Astra high for medium-tough work; GPT-6 Pro web for tough, architectural and research work. The legacy `prepare-sol-pro-architecture-review` identifier does not choose a historical model. No silent effort or transport substitutions.

## D003: Actual two-model review and local implementation

**Owner requirement, with engineering safeguards.** Pro and Fable co-produce an agreed solution through the separate review repository and the case's same Pro chat. Immutable turns and exact-digest approvals enforce version identity. The original local Codex session reconciles unknown local facts, implements and verifies. Agreement is not empirical proof or permission for unrelated external changes.

## D004: Local SemIf as decision support

**Owner requirement, with selected engineering scope.** SemIf runs locally. Hard policy, permissions, requirements and tool evidence remain outside learned control. Initial extensions prioritize context selection, requirement gaps, next diagnostics, local drift and review triage. All nine catalog operators begin in shadow mode; promote each only with workload-specific evidence.

## D005: Small coordinator before optional extensions

**Engineering baseline.** Preserve the custom Codex, use one local coordinator, ordinary Git and transactional local state. Add provenance-aware memory, approved diagnostic playbooks, isolated counterexamples and specialist training only when measured benefits justify them. More agents are not a goal in themselves.

## D006: Manual Pro transfer until automation is qualified

**Recorded capability gate, not a change to the owner's target.** The supplied kit documents the dated Computer Use limitation and provides a manual ZIP/prompt path. Automatic upload and same-chat continuation require a supported, permitted and tested transport. Follow [the gate](COMPUTER-USE-GATE.md); do not introduce a restriction bypass.

## D007: Public development context, private execution context

**Engineering/privacy boundary.** Publish generic source and sanitized evidence. Keep credentials, chat bindings, customer data, live case exports and machine-specific state private. The `GPT-Pro-Escalation` template is included; creating that repository or exporting real case data is not performed by this publication. No license choice is silently added.

## Future entries

For each substantive change, record the date, proposal, evidence, affected requirements, alternatives considered, authority/owner decision, implementation references, tests and rollback. Keep minor mechanical changes in the ordinary Git history rather than inventing a design decision for every edit.
