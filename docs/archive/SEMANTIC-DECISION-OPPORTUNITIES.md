# Useful CLM operators beyond model routing

These are proposed workflow applications, not measured workstation improvements. The local contrastive backend makes repeated state/action comparisons practical; its existence does not prove each application is useful. All nine operators in `config/decision-operators.json` start in shadow mode.

## Initial adoption order

**Context relevance and missing context.** Retrieve candidates with ordinary search, indexes or embeddings, then compare their relevance to the current requirement. Keep mandatory requirements and approved invariants pinned. Retain source paths, revisions and the ability to expand omitted evidence. Compare against conventional retrieval, not only a weak no-retrieval baseline.

**Requirement evidence gaps.** Ask whether supplied evidence supports, contradicts or leaves a requirement unresolved. A reconnect test does not establish persistence across restart. The operator suggests the missing check; actual execution establishes whether the requirement holds.

**Next diagnostic.** Select a predeclared scoped investigation, such as a reproduction or inspection of the transaction boundary. Return only the capability ID. Tool arguments, permissions and execution remain deterministic. Prefer an informative experiment over repeated speculative rewrites.

**Local drift.** Compare the accepted solution with newly discovered local facts and the actual implementation diff. Suggest review of potential mismatches; let the coordinator classify mechanical adaptation versus a material design change requiring renewed Pro/Claude review.

**Review triage.** Suggest links between overlapping objections and relevant evidence. Preserve every original finding and its disposition. A duplicate suggestion cannot close an objection or produce agreement.

## Later, separately evaluated operators

**Provenance-aware memory.** Keep immutable observations with revision/time/scope and proposed relationships in separate records. Contradictions trigger inspection. A model summary is not a new owner instruction, and a previous observation is not current truth merely because it is similar.

**Candidate-test selection.** A local generative helper may propose a few failure cases in an isolated workspace. CLM can rank relevance/novelty, but the approved behavior contract defines the oracle and actual tests determine results. Never generate a test that silently redefines correctness.

**Attention triage.** Surface a bounded set of unresolved items at useful workflow boundaries. Do not hide mandatory approvals or create unattended background claims.

**Approved playbooks.** Pro and the selected Claude reviewer can co-produce a finite diagnostic tree. CLM chooses among its already-permitted branches from current observations; the coordinator enforces preconditions, termination and budgets.

## What changes with CLM

The [pinned upstream](https://github.com/Contrastive-LM/CLM/tree/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7) separately represents states and actions, enabling reused action vectors and cheap ranking after encoding. Long-horizon verifier demonstrations use selected candidate solutions and specialized training on small held-out sets. They do not establish zero-shot routing quality, latency on this GPU, or independent code generation.

No old backend calibration, latency claim or prefix-reuse result is carried forward. Questions that depend on future tool output still wait for it. Independently answerable questions may share context, but different questions change the state-side text. Cache reuse must match actual text/deployment identity rather than an assumed universal shared prefix.

## Learning specialists

Only after a decision family earns its place, collect independently verified outcomes and train a small task-specific head offline. Split by task/project and time; keep a held-out calibration/evaluation set. A teacher's choice alone is not ground truth. Promotion requires a quality/resource comparison, canary and rollback, and never changes hard policy automatically.

See [decision-plane contracts](DECISION-PLANE.md), [CLM integration](CLM-ADAPTER.md), [evaluation](DECISION-EVALUATION.md) and [model evidence](MODEL-EVIDENCE.md).
