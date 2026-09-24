# SemIf adapter

SemIf is a local, open-source typed-decision component. AgenticArch does not require a hosted decision endpoint, remote key, or per-decision subscription.

## Verified interface and limits

The upstream README inspected on 2026-09-24 documents a `semif-score` command accepting JSONL records with `id`, `state`, `question`, and `options` (`id` and `description`). It documents direct scoring and alternative reuse modes, and recommends workload validation of option probabilities. The reference is in `INTEGRATION-REFERENCES.md`.

Do not assume an HTTP server, `/decide` endpoint, a stable Python import path, a calibrated confidence field, or identical output schemas across upstream revisions. Discover the installed version and inspect a real result before implementing the wrapper. Prefer reuse of the owner's existing installation.

An example upstream-shaped request:

```json
{
  "id": "task-example-intake-1",
  "state": {
    "goal": "Implement the specified validation rule",
    "risk_assessed": true,
    "mandatory_pro_categories": [],
    "known_contract": "Reject invalid inputs without changing the API schema"
  },
  "question": "Which permitted implementation lane best fits the remaining work?",
  "options": [
    {"id": "luna_low", "description": "Routine mechanical edit with no unresolved design."},
    {"id": "luna_high", "description": "Bounded implementation or isolated debugging."},
    {"id": "astra_high", "description": "Medium-tough implementation within known architecture."},
    {"id": "pro_web", "description": "Tough problem or unresolved architecture/research/design."}
  ]
}
```

The task facts in `state` come from the controller's intake/evidence pipeline. Repository text is labelled untrusted content. The request does not ask SemIf to decide whether a compiler ran or whether the owner granted permission.

## Local wrapper contract

Implement `score(request) -> DecisionAdvice | Unavailable` behind an adapter protocol. `schemas/semif-advice.schema.json` is **AgenticArch's normalized response**, not the upstream wire format.

The normalized response contains a schema version, request and state digests, the exact ordered options, a selected option, finite option scores in [0,1], model/backend provenance, and a calibration status (`uncalibrated` or `workload_validated`). Preserve upstream raw output privately for debugging. A field named `confidence` upstream must not be relabelled as a probability of correctness.

Validate the option set, the selected argmax (within a defined numerical tolerance), total probability within tolerance when upstream returns a distribution, request identity, and provenance. Tie behavior and ties to a deterministic policy; default to the safer higher lane for equal routing scores. No undocumented option or mixed task result is accepted.

## Deployment choice

Begin with the existing pinned local backend in direct mode. The upstream documents native MLX for Apple Silicon and GPU paths for other environments. Select the backend actually installed; model size and quantization are owner-local configuration, not public universal defaults. Do not download new multi-gigabyte models silently.

An initial subprocess adapter may run the verified CLI with temporary JSONL files, strict timeouts, a controlled environment, and no shell interpolation. This is acceptable for correctness testing, but model reload overhead may make it unsuitable for per-task production use. Once measured, reuse an existing persistent scorer or add a single resident worker around a verified public Python interface. Do not invent a network service merely to keep a model loaded.

Default transport is in-process or a local process/Unix socket. An explicitly configured loopback endpoint is permissible after authentication and origin checks. Off-device inference is a different export boundary and is disabled by default; no silent hosted fallback.

Record cold-start and warm latency separately. Use direct mode first; enable prefix/shared reuse only after exact-state cache-key validation and workload equivalence testing within numerical tolerances. Faster execution is not assumed semantically identical.

## Evaluation and calibration

Build a labelled set from actual coding task boundaries after redaction. Include easy cases, architecture/research masquerading as small edits, ambiguous failures, and out-of-distribution projects. Split by task/project and time so variants of one task do not leak across training, calibration, and evaluation.

Measure wrong-lane rate, missed mandatory escalations, unnecessary escalation, abstention, coverage of an accepted score threshold, latency, and changes in real accepted-task outcomes. A held-out calibration report must identify the model, backend, prompt/option version, and task distribution. Estimate uncertainty; small samples do not establish rare-error safety.

The initial release uses no calibrated-score completion threshold. Score-based automation can be added only through an explicit policy review; deterministic checks and mandatory Pro routing remain non-waivable. Hold out both successful and failed tasks, not only tasks the system completed.

## Failure behavior

Timeout, GPU pressure, out-of-memory, missing weights, invalid schema, or stale output -> mark SemIf unavailable, retain a bounded diagnostic, and use deterministic routing floors. Do not restart indefinitely, kill unrelated AI workloads, downgrade an architecture task, or fabricate an advice result. Use at most the configured local recovery attempts and then open the circuit until a health check succeeds.

## Semantic operator extension

`config/decision-operators.json` and `reference/decision_plane.py` define a separate AgenticArch request envelope for context, evidence, diagnostics, memory, drift and review triage. It is not an upstream wire schema and does not replace `semif-advice.schema.json`. Map each normalized request to the installed `id/state/question/options` scorer interface, then bind the returned scores to the complete request digest. Authenticate and inspect the actual local adapter before trusting provenance.

Respect the discovered option limit; the supplied catalog fits the documented 2–16 option baseline. Group only identical state projections and execution context. A downstream question requiring a tool result must wait. Shared-state scoring, tournaments and calibration each need their own qualification. A high score is neither authorization nor completion. See [decision plane](DECISION-PLANE.md).
