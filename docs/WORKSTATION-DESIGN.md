# Workstation-first design and optional extensions

## Recommended implementation

Keep the existing custom Codex as the user-facing coordinator. Add a **small, explicit control layer** to its verified extension point, or use a local stdio sidecar when changing the fork would create unnecessary maintenance. Do not replace a working local/remote provider bridge merely to match a new framework.

The control layer owns policy, task identity, permissions, evidence, GPU scheduling and escalation. Model reasoning is a replaceable worker capability, not the authority layer. The reference design is meant to use the 96 GB GPU effectively without requiring all available memory, a model farm, or a second machine.

```text
Custom Codex: original task, local context, user interaction
    |
    +-- deterministic controller + SQLite + evidence/object directory
    |       +-- policy floors -> Luna low/high or Astra high
    |       +-- required deep work -> Pro web case -> Fable <-> Pro
    |       +-- verification plan -> tests/build/type checks/behavior
    |
    +-- local helper pool, bounded and sandboxed
            +-- SemIf: typed route/retry/review advice
            +-- context index: paths, symbols, dependencies, source spans
            +-- optional draft worker: proposed patch in separate worktree
            +-- optional counterexample worker: candidate tests/reproducers
            +-- resource scheduler: measured capacity, cancellation, priority
```

Local helpers may gather evidence and propose alternatives **within an approved scope**. They do not bypass the required main coding lane, make architecture decisions in place of Pro, publish changes, change policy or approve completion. Their outputs have the same untrusted-candidate status as any generated artifact.

## Core improvements to implement first

### Evidence packets with source anchors

Build context from exact source spans, Git revisions, locked requirements, command receipts and known unknowns. A local index can accelerate retrieval, but exact search and dependency traversal come first. A summary always links back to its evidence. Record path, line range where applicable, content digest, source class and timestamp. Revalidate stale facts; do not treat a vector search hit as authoritative or complete.

This makes both cheap workers and remote reviewers useful: they receive the relevant facts instead of an indiscriminate repository dump. Unknowns are first-class entries. Stable context may be reused; changed requirements, source bytes, tool versions and redactions invalidate the appropriate cached entry.

### Verification-directed repair

Classify a failed check as code defect, environment failure, missing capability or uncertain evidence. A coding retry must propose a concrete hypothesis and a discriminating check. Missing network access or dependencies does not justify paying a stronger model to repeat the same failing command. Keep the accepted check plan separate from candidate-added tests so a worker cannot make itself pass by weakening the tests.

### Exact local return

Pro/Fable approve a design at known versions. Local Codex produces a reconciliation record comparing that design with the actual workstation/project. Mechanical adaptations preserve invariants; changed data semantics, security, architecture or rollback guarantees trigger focused review. This is essential because remote agreement is not knowledge of the live machine.

## Optional extensions, enabled by measurements

| Extension | Useful work | Boundary and promotion evidence |
| --- | --- | --- |
| Local context retrieval | Rank source spans and relevant tests for the current task | Show improved relevant-context recall or lower wall time on held-out tasks; keep exact-source fallback |
| Local patch speculation | Try a narrow candidate in an isolated worktree while the main lane considers another hypothesis | No writes to the main worktree; compare actual tests and accepted outcome, not rhetorical quality |
| Counterexample workshop | Generate adversarial inputs, property tests, fuzz seeds and failure/recovery scenarios | Run in a restricted sandbox with resource limits; independent review of test validity and acceptance coverage |
| Changed-surface risk assessor | Ask SemIf several bounded questions over the same state | Benchmark direct versus shared-prefix modes; keep deterministic hard-trigger checks; avoid correlated scores pretending to be independent votes |
| Case retrieval | Retrieve prior resolved patterns and their acceptance evidence | Scope by project/permissions; stale advice is evidence only; never transfer secrets or obsolete approvals |
| Learning from outcomes | Fit SemIf calibration or compare routing policies offline | Separate training/calibration/holdout sets by task/project; explicit versioned promotion; no automatic live policy mutation |

These are proposed experiments, not established performance claims. Implement one extension at a time after the baseline works. Prefer removing an extension that increases rework, latency or administration. A swarm, autonomous self-modification, or a large persistent graph database is not a default requirement.

## GPU and host scheduling

Discover actual GPU, driver, CUDA/runtime support, free memory, display/BMC usage, other workloads and local serving interfaces. Use the installed SemIf backend initially; a pinned small checkpoint may be sufficient, but its quality must be tested on this coding workflow. [SemIf upstream](https://github.com/TheoLeeCJ/SemIf) describes local scoring backends and workload calibration; it does not establish performance on this workstation.

A GPU admission decision must account for weights, worst permitted context/KV cache, runtime workspaces, activation peaks and a measured safety reserve. Do not fill nominal VRAM with weight files and assume the model will run. Start with one heavy local generation job at a time; allow resident SemIf concurrently only after measuring the combined peak. All numeric limits are local configuration and experimentally qualified, not universal guarantees.

Priorities: preserve the user's interactive session and existing workloads, keep small decision calls responsive, then admit optional speculative work. Cancel optional jobs before the main task is starved. On OOM, record the event, stop admission, release the affected worker, reduce a reviewed resource envelope and retry at most within the job policy. Never silently truncate evidence/context or offload private inputs to a remote model. A cold local model may be slower overall than the mandated remote lane; include loading and contention in measurements.

Use loopback/Unix sockets or inherited stdio for local helpers. No externally reachable model endpoint is required. Keep model downloads/version pinning explicit, secrets out of logs, and existing AI services untouched until their replacement is justified and authorized.

## Evaluate the whole workflow

Compare a policy-only baseline against +SemIf, then +retrieval, then +counterexample work. Use representative tasks from the owner's projects after redaction and explicit data-use approval. Record task acceptance, regressions, rework, wall time, human intervention, remote usage, local cold/warm latency, GPU occupancy and blocked/paused cases. Report uncertainty and denominators; exclude no failed cases merely because the loop paused.

Choose the simplest configuration that improves accepted outcomes under the owner's time/cost constraints. Do not optimize a toy routing benchmark while making the real coding loop worse.

## Permission to amend the setup

The owner is open to improvements. Inventory the custom fork and existing integrations first; propose a small reversible change with expected benefit, qualification test and rollback. Preserve the fork's local-model support. Reuse the existing Fable bridge, custom tool registry, sandbox and model selection mechanisms when sound. New architectural choices belong to the Pro/Fable review path, using manual Pro transfer while the automatic transport remains unsupported.

## Research-backed decision-plane extension

The selected expanded design uses SemIf for local semantic control, beyond lane selection. Prioritize context retrieval, requirement evidence, diagnostic selection, debate triage and drift; then version-aware memory and approved playbooks. Local test-candidate generation and small predicate-model training are separate experiments, not mandatory first-release complexity. See [opportunities](SEMANTIC-DECISION-OPPORTUNITIES.md) and [evaluation gates](DECISION-EVALUATION.md).
