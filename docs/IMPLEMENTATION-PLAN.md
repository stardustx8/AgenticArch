# Implementation plan

## Working approach

Deliver a small local coordinator, not a new agent platform. Preserve installed Codex and SemIf integrations. Use a single target worktree and one coordinator per case. Implement and verify incrementally; do not claim live capability based on this kit's offline tests.

A resolved path or executable is discovered locally; it is never guessed from an example. Keep discovery results in private local state. No real environment report is committed to this public repository.

## Phase 0 — inventory and safe bootstrap

Read the master implementation prompt, `docs/OWNER-REQUIREMENTS.md`, `docs/WORKSTATION-DESIGN.md`, `docs/COMPUTER-USE-GATE.md` and specifications. Record the installed Codex client/version, supported model IDs and effort levels, effective auth mode, Computer Use availability, existing skill directories and helpers, Fable provider/model, SemIf installation/revision, Python versions, Git authentication, target worktree status, and review-repository access/visibility.

Use `codex --help` and supported discovery, not a model's assertion of its own identity. The web lane requires visible GPT-6 Pro selection and a verified account; public documentation does not prove this account has that capability. Do not use the API as a covert replacement for Pro web.

Do not replace the owner's skills blindly. First read their complete trees, preserve helpers and names, back up all replaced bytes outside the public repository, and generate a local installation diff. The requested deliverables are actual revised skills, not prompts instructing someone else to revise them. Skill originals must be available before claiming that their behavior has been preserved. Do not create competing same-named skills in multiple discovery locations.

Create or use `GPT-Pro-Escalation` only within the owner's authorization. Use private visibility for real cases; never change existing visibility automatically. Verify read, branch creation, commit, non-force push, and readback using an explicitly approved synthetic case. Read access alone is insufficient.

Deliverable: private capability report with `available`, `unavailable`, or `not_tested` per capability; backups and reversible installation plan. Unknown model IDs remain null and disable dispatch.

## Phase 1 — enforce the local coding loop

Implement policy loading/validation; persistent task state; single-writer locking; scoped worktrees; Codex dispatch; verification-plan locking; exact evidence records; routing and retry logic; local CLI. Use the pure functions in `reference/core.py` as a tested specification, not as a complete security boundary.

Preferred CLI contract to implement:

```text
agenticarch doctor
agenticarch run --project <path> --request-file <file>
agenticarch status --task <id>
agenticarch resume --task <id>
agenticarch cancel --task <id>
agenticarch case inspect --case <id>
```

These commands are the target interface, not installed commands in this kit. Start without a daemon. Require a real, sandboxed Codex dispatch to prove each configured coding lane. A model or effort mismatch invalidates that dispatch. Honor existing approvals and sandbox policies; never add unrestricted flags to make automation convenient.

Persist task, pass, event, check, outbox, and case records in SQLite transactions. Outbox operations have unique operation IDs and destination/input hashes. A completed pass is counted once. Detect snapshot changes during verification. Preserve pre-existing edits; never `reset --hard`, auto-stash unknown changes, or force-push.

Gate: route tests, evidence tests, worker failure tests, restart tests, and one synthetic end-to-end coding task pass. Required checks are locked and nonempty. No remote escalation is declared ready yet.

## Phase 2 — connect SemIf in shadow mode

Wrap the installed CLI or verified Python interface. Capture actual input/output fixtures with secrets removed. Normalize to the versioned AgenticArch contract. Keep a resident backend only after measuring load overhead; do not add a network service by default. Direct scoring is the initial mode.

Compare advice with deterministic routing on realistic labelled cases. Do not let a raw score authorize completion. Test missing weights, timeout, malformed output, cache mismatch, option ordering, and model/backend changes. Benchmark cold and warm latency separately and include GPU resource contention.

Gate: local-only calls verified; no remote fallback; advice cannot lower mandatory floors; failures degrade to deterministic behavior, not false success. Promote from shadow to advisory routing only after an explicit recorded decision.

## Phase 3 — install and connect the two skills

Install the shipped `prepare-sol-pro-architecture-review` and `fable-adversarial-review` revisions and integrate them with the controller; retain manual ZIP/prompt transfer as a recovery mode. Skills can be followed by a real local agent even before all automation exists, but no unimplemented controller command may be presented as working.

Implement allowlisted snapshot export, redaction inventory, content approval, reproducible ZIP, case branch setup, Computer Use transport, chat binding, end-of-turn detection, Git-native/relay writes, and per-turn readback. The owner grants a scoped policy once for specified data classes/destinations; only changed scope, secrets, or other elevated actions require renewed approval. Avoid needless confirmation on every ordinary round.

First validate a synthetic manual round and same-chat manual continuation. Standard Computer Use currently excludes automating ChatGPT itself; automatic first-send/continuation tests remain BLOCKED_CAPABILITY until a permitted supported path is documented and verified. Only then test the automatic equivalents. Validate model selection on every send. Do not automate login, CAPTCHA bypass, payment, permission expansion, or credential extraction.

Gate: exact approved bytes reach the correct case/chat once; a real Pro contribution is durable; all interruption scenarios leave a resumable checkpoint. The browser test must use the actual local interface, not only a mock.

## Phase 4 — adversarial convergence and local return

Implement alternating actual Fable/Pro invocations, shared `DIALOGUE.md`, immutable turns, controlled write windows, rebuttal/finding tracking, solution manifests, and matching approvals. Freeze the proposed solution file set before collecting final approvals. If a model edits any included file, compute a new digest and collect both approvals again. Fable challenges at least once and Pro responds at least once.

Use a unique private conversation binding and exact case IDs. Resume after quota/login interruptions in the same conversation. Budget exhaustion is `PAUSED`, never `CONVERGED`; explicit resumption can continue the debate without losing history.

Fetch the agreed commit into the original local task, inspect local deltas, implement faithfully, and reverify. Mechanical adjustments may proceed with a recorded rationale; altered architecture, security, data semantics, acceptance or rollback guarantees reopen focused review in the same case/chat.

Gate: real two-model synthetic case, crash/restart at each side-effect boundary, stale-approval rejection, pinned-result fetch, and final local acceptance report all pass.

## Phase 5 — limited rollout and operations

Begin with harmless projects and supervised execution. Record successful accepted tasks, regressions, rework, routing mistakes, elapsed time, human intervention, model usage where available, SemIf latency, debate rounds and pauses. Do not invent dollar savings, subscription capacity, or accuracy from hypothetical task distributions.

Retain owner-only checkpoints for recovery. Define cancellation, backup, retention, and upgrade procedures. Keep production/project commands behind the same explicit authorization rules as ordinary Codex. Broader rollout requires local evidence, not confidence prose.

## Delivery rule

Finish with the exact commit, check results and remaining limitations. Keep `main` current when authorized and unprotected; honor required review rules otherwise. Never claim a pushed repository if only a local commit exists. New architecture questions arising during implementation follow the Pro workflow; a missing bridge uses the established manual path rather than silently downgrading the task.

## Phase 6 — optional workstation enhancements

After the core loop works, evaluate the local evidence index, counterexample workshop and narrowly scoped patch speculation from `docs/WORKSTATION-DESIGN.md`. Keep one heavy GPU job initially, measure combined SemIf/worker memory peaks, and preserve existing AI workloads. Compare accepted outcomes with the policy-only baseline before enabling each addition. Never let an optimizer silently change owner requirements or production policy.

## Phase 2A — bounded semantic decision extensions

Read the researched opportunities, decision-plane contract and evaluation plan. Add scoped event hooks to the custom Codex integration and map the supplied operator catalog to the installed SemIf scorer. Start with context relevance, requirement gaps, next diagnostics, drift and objection triage. Run in shadow mode until each family has representative local evidence. Use `reference/decision_plane.py` for request identity, independent batching and advisory-response validation, not as a complete runtime.

Keep mandatory evidence, model floors and participant approvals outside learned control. Add version-aware memory only after provenance/invalidation; add approved playbooks/counterexamples later. Specialist training remains offline and opt-in. This phase may follow the core end-to-end loop when it would otherwise delay a working system. Record each family's mode and actual acceptance evidence.
