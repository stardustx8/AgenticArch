# Bounded semantic decision plane

Status: target integration specification with an offline reference subset. Required model routing and the Pro/Fable protocol remain unchanged.

## 1. Architecture

```text
Owner requirements + approved plan + live local capabilities
                         |
                deterministic coordinator
                         |
       immutable event/snapshot + provenance registry
              /          |              \
     direct tools   SemIf decision     permitted local
                    operators          generative helpers
              \          |              /
           observed evidence + advisory proposals
                         |
              policy/capability validation
                         |
   permitted coding lane / diagnostic / Pro-Fable turn / pause
```

The custom Codex integration publishes events and consumes advisory proposals through an in-process API or local stdio sidecar. A dedicated daemon, message broker, vector service or graph database is unnecessary initially. Keep one coordinator in charge of state transitions. Existing functions in `reference/core.py` remain the hard routing/convergence/completion reference.

## 2. Five boundaries that must not blur

**Observation** is measured or retrieved data with provenance. **Predicate** is a fallible semantic judgment over that data. **Proposal** is an allowed next step suggested by a predicate. **Authorization** is a user/controller policy decision. **Verification** is evidence collected by actual checks on the current snapshot.

A `supported` predicate is not an observed PASS. A high-ranked action is not authorized. A suggestion to re-check a requirement does not rewrite it. A Pro/Fable consensus is not evidence the local implementation passed. Represent these as different types/records, not a single `confidence` field.

## 3. Event and snapshot contract

Emit events at meaningful boundaries: `intake`, `context_ready`, `verification_failed`, `implementation_pass`, `review_turn`, `observation_added`, and `case_return`. Do not call SemIf after every file read or on an arbitrary fast timer.

A projection contains only the allowlisted evidence required by one operator. Record project/task/case IDs, requirement/plan/target snapshot digests, evidence IDs/ranges, source freshness, observed-vs-inferred status, and the authorization-scope digest. Preserve raw logs locally; send short bounded excerpts to a scoring backend. Missing context is represented as missing evidence, not replaced with invented facts.

Events are deduplicated by exact content/state identity. A changed requirement, source revision, policy or permission invalidates affected pending results. Never reuse a score across projects or authorization scopes merely because the visible text matches.

## 4. Operator catalog

`config/decision-operators.json` defines stable operator IDs, triggers, projections, atomic questions, exact option menus, fallback and permitted influence. All entries start in shadow mode. It is an AgenticArch contract, not SemIf's upstream API.

Use four main operator forms:

- `assess`: a small enum, usually supported/contradicted/insufficient or analogous states;
- `rank`: select an ID from a prefiltered candidate set with an explicit abstention option;
- `relate`: propose a typed relationship between two provenance-bearing observations;
- `choose_probe`: select a known diagnostic capability ID, never emit executable arguments.

Separate independent semantic axes. For example, novelty, relevance and severity should not be compressed into a single “good?” question. Do not ask the classifier to author rationales; evidence references are input metadata. When an explanation is necessary, send the observation and judgment to the appropriate generative lane.

## 5. Shared-state batching and bounded speculation

Start with direct mode as the baseline. Group questions only when their serialized state projection and complete execution context match. Enable prefix reuse/parallel suffixes only after equivalence and resource tests for the installed backend. Use its discovered supported option count; this catalog conservatively caps menus at 16, including abstention, matching the inspected baseline.

A speculative question is valid only if answerable from current state. For example, “does this error suggest a transport failure?” and “does this error mention persistence?” can be asked together. “Did the reconnect test pass?” cannot be asked until that test runs. Interpret a counterfactual output only inside the branch whose preconditions hold.

Use finite event budgets, backpressure, GPU admission checks and cancellation. Additional questions consume memory and compute even without output tokens. Do not batch thousands of source pairs or all possible branches. Prefer deterministic candidate narrowing, then semantic judgment. No O(n squared) memory linking or tournament over an entire repository by default.

## 6. Cache identity and qualification

The reference request builder hashes the full operator definition, exact projected state and an execution context containing project/task identity, snapshot, requirement, policy and scope digests, backend/model/tokenizer/quantization/runtime/prompt versions, scoring mode, calibration identity, and option limit. It rejects non-JSON data and nonfinite numbers.

Production adapters additionally record the actual prompt/template digest, source content checksums, scheduling/numerical settings and receipt. An old calibration artifact cannot be silently reused after a model, prompt, backend, option schema or workload change. Similarity-based caching may retrieve old evidence; it cannot replay privileged actions, approvals or proof of completion.

## 7. Advisory action handling

The reference selector returns an `ADVISE`, `SHADOW`, `ABSTAIN` or `FALLBACK` record; it never executes anything. Results are bound to the complete request digest and exact options. Malformed scores, NaN, wrong option sets, ties and stale IDs abstain. Calling code must already have authenticated the local backend; a well-shaped response is not authentication.

Initially, all proposals are logged only. After family-specific qualification, low-consequence suggestions may change context ordering or diagnostic priority. Hard-blocked actions never enter a model's menu. The actual executor checks permission, path scope, current capability and snapshot again immediately before action. Missing memory or environment facts should generally trigger retrieval/inspection, not escalation to a more expensive model pretending to know them.

No operator can lower an owner model floor, close a material objection, remove a mandatory check, authorize upload, change a requirement, approve a solution, or mark a task complete. A learned warning can request investigation; it is not a new owner requirement.

## 8. Context and memory

Start with existing scoped search, AST/import indexes where available, SQLite observations and optional embeddings. Each record has immutable original content/ref, project scope, time/revision and source authority. Suggested relationships are separate rows. Exact temporal/order/identity relations use software; ambiguous relevance or contradiction may use SemIf.

Pinned requirements and mandatory evidence are always included in a handoff pack. Preserve the ability to expand a filtered pack. Inferred memories, model claims and customer documents are never promoted to user instructions. Requirement changes come only from an authorized owner decision, not semantic similarity.

## 9. Local GPU and model roles

Use the existing SemIf installation and custom Codex provider registry. Measure actual cold/warm prefill, peak memory and workload interference on the owner's 96 GB GPU. Keep one heavy optional generative job initially, with a configurable resource reservation for interactive work. Do not assume model weights alone determine memory fit.

Optional local models produce evidence summaries, candidate tests or retrieval embeddings. Their outputs retain provenance and are not substitutes for required Luna/Astra/Pro work. Pro/Fable approve consequential architecture changes. A scheduling policy may postpone an optional helper, but cannot silently swap the requested model family.

## 10. Interaction with the two skills

Before Pro handoff, use the local layer to propose evidence gaps and the most relevant scoped attachments. The exact manifest, redaction, approval and export controls still apply. The reviewer sees explicit missing evidence and can request expansion.

During Fable/Pro turns, use it to propose objection links and relevant new evidence. Original turns and objections remain intact. Required replies and approval digests cannot be filtered out. At case return, use semantic drift signals to focus `LOCAL-DELTA.md` review; let the original Codex session decide within scope and reopen material changes.

## 11. Deployment stages

Implement the dependency-free contracts and offline fixtures first; connect actual SemIf in shadow mode second; conduct representative held-out evaluation third; activate each advisory family separately fourth. Keep rollback to the deterministic baseline immediate. Training, graph expansion and speculative local workers are later, independently qualified features.

See [research and priorities](SEMANTIC-DECISION-OPPORTUNITIES.md), [evaluation](DECISION-EVALUATION.md), and `reference/decision_plane.py`. The latter is not the complete orchestrator, runtime adapter, safe file collector, durable queue or security boundary.
