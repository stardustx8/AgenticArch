# Semantic decision models: useful opportunities for AgenticArch

Research date: **2026-09-24**. This document separates published capabilities, early experiments and proposed engineering applications. The applications below are a design recommendation, not measured performance on the owner's workstation.

## The opportunity

Make SemIf more than a model selector. Use it as a local **semantic decision plane**: a small number of reusable, bounded questions about current evidence whose answers help ordinary software choose the next useful step. Open-ended design and reasoning remain with the prescribed Luna/Astra/Pro lanes; tests and policy remain deterministic.

The important primitive is `state + criterion + declared alternatives -> option scores`, without generating an explanation or patch. SemIf's published method reads allowed answer-token logits from a frozen language model. This reproduces an interface pattern; it does not establish that it shares an undisclosed specialist architecture or training recipe. Its published baseline supports 2–16 described options. [S01]

Neither classification nor model routing is new. Earlier work such as RouteLLM already used learned routing, and SayCan combined semantic desirability with available skills. The practical opportunity here is runtime-defined criteria, compact typed answers, and shared-state computation that can make more frequent semantic decisions affordable. Exact cost and latency depend on the deployed backend. [S04, S09]

## What the evidence supports

| Evidence | Practical implication | Boundary |
| --- | --- | --- |
| SemIf's direct scorer, reusable state prefix, and parallel suffix experiments | Evaluate several well-scoped criteria about one snapshot without producing prose | Reuse modes can change close decisions; benchmark the actual quantization, batch shape and GPU contention [S01, S02] |
| Typed questions and speculative fan-out patterns | Compute independent observations together; discard irrelevant observations in code | A question that requires another answer or new tool output is a later stage, not an independent sibling [S05, S06] |
| Original goal-hierarchy and tournament experiments | Keep a stable goal while making cheap tactical choices; shortlist large candidate sets in stages | Small demonstrations, not proof of coding-agent reliability; tournament grouping can discard the best candidate [S07] |
| A September 21 memory-control preprint | Use bounded decisions to organize and retrieve memory, rather than asking a generative model to narrate every memory operation | Early conversational-memory research, not local SemIf/coding validation; do not copy its numerical gains into planning [S08] |
| Workload-specific calibration results | Evaluate each decision family separately and allow abstention | Calibration changes probability quality, not the selected answer's correctness [S03, S11] |

## Ranked applications

The ranking reflects expected usefulness **for this architecture**, not benchmark scores. “First” means first semantic extensions to evaluate after the deterministic core, not automatic production activation.

| Rank | Application | Why it is valuable here | Stage |
| --- | --- | --- | --- |
| 1 | Adaptive evidence retrieval and context packing | Give each coding/review model the relevant code, contracts, tests and local facts; reduce missing-context mistakes | First |
| 2 | Requirement-to-evidence gap detector | Notice when passing tests do not address an explicit requirement | First |
| 3 | Next-diagnostic selection | Replace repeated speculative fixes with a discriminating test or inspection | First |
| 4 | Version-aware local project memory | Reuse previous discoveries without silently reusing obsolete assumptions | Next |
| 5 | Pro/Fable disagreement triage | Spend debate effort on actual unresolved claims and counterexamples | First |
| 6 | Plan and local-implementation drift sensing | Detect changes that no longer preserve the agreed solution | First |
| 7 | Approved diagnostic playbooks | Execute familiar investigations with fewer open-ended model turns | Next |
| 8 | Counterexample/candidate prioritization | Use the local GPU to find informative failures before another Pro round | Experiment |
| 9 | Semantic event filtering and interruption triage | Surface blockers without forwarding every log line or harmless change | Next |
| 10 | Outcome-grounded small specialist models | Distil frequent successful predicates into cheaper local classifiers | Later experiment |

### 1. Adaptive evidence retrieval, not just a bigger context window

For a task such as making job submission survive connection loss, first retrieve candidates using exact symbols, imports, lexical search and existing embeddings. SemIf then judges candidate relevance, contradictory-version risk and which known evidence category is still missing. Keep owner requirements, active contracts, explicit exclusions and mandatory evidence pinned regardless of relevance score.

Feed the smallest **sufficient and auditable** pack to the selected worker or Pro. Include source path, revision, range and content digest, not an unverifiable summary. Retain an omission index so the reviewer can request more. Preserve permission boundaries before retrieval: unrelated/private material must never enter the candidate set merely because it is nearby on disk.

For large candidate pools, evaluate direct ranking, a conventional reranker, and small tournaments with top-k retention and order randomization. Do not assume SemIf beats a retrieval-specialized model. High-quality retrieved context can help coding, but retrieval itself can miss important files. [S10]

**Acceptance:** improve evidence recall at the same token budget and accepted task outcomes; detect deliberately omitted relevant evidence; never omit pinned requirements. **Failure fallback:** ordinary scoped search and explicit missing-context reporting.

### 2. Requirement-to-evidence gap detector

Represent each requirement separately. Ask whether its associated code, observed checks and evidence support it, contradict it, or leave it unresolved. For example, a happy-path unit test does not establish that an interrupted submission cannot create duplicate work.

This is a semantic gap detector, not a test oracle. The controller verifies that files and test results exist and match the snapshot. The coding model or reviewer inspects suspected gaps and adds meaningful tests. A SemIf `supported` result cannot mark the requirement complete by itself.

**Acceptance:** planted omissions and false “done” claims are surfaced, including tests that assert the wrong behavior; measure both missed gaps and review noise. **Failure fallback:** retain the explicit checklist for the worker/reviewer.

### 3. Next-diagnostic selection: investigate before escalating blindly

A failed task may need more reasoning, but may instead lack one fact. Give SemIf an approved finite menu: inspect the transport retry path, reproduce a lost response, inspect the idempotency contract, compare dependency versions, or report insufficient information. Every menu item resolves to an existing scoped read/test capability. The classifier never writes a command string.

Use it to propose the **next useful observation**, not to guess the root cause. A permitted runtime tool gathers the observation; only then can a dependent decision run. Once outcomes are logged, evaluate which proposals actually disambiguate failures. A probability over menu choices is not an estimate of expected information gain or probability that a fix will work.

**Acceptance:** reduce unsuccessful repair passes or time-to-reproduction without suppressing mandatory checks. **Failure fallback:** worker-directed diagnosis. Architecture and research still go directly to Pro.

### 4. Version-aware memory, with facts that can become stale

Keep a local evidence store of observed failures, validated remedies, owner decisions, interface constraints and unresolved assumptions. Exact identifiers and timestamps are handled by software. SemIf suggests relations such as relevant, possibly contradictory, superseded candidate, or unrelated.

Retain the original observation and provenance. “Superseded” is a proposed relation, not permission to erase history or turn an inferred statement into an owner decision. A previously successful recipe is a search candidate; changed dependencies, environment or requirements force revalidation. Start with SQLite, lexical search and optional embeddings. A multi-graph database is not required.

A very recent memory paper supports investigating this separation of fast control, stored evidence and slower synthesis. Its current presentation includes inconsistent narrative/table values; treat it as architectural inspiration pending reproduction, not an established quantitative advantage. [S08]

**Acceptance:** retrieve useful prior fixes while rejecting seeded stale facts; test privacy isolation and contradiction retention. **Failure fallback:** raw searchable observations without learned relations.

### 5. Pro/Fable disagreement triage

For each new turn, suggest links to existing objections, identify possibly new evidence, and flag claims that still lack support. Do not send a flattened “overall quality” score. A claim-level queue lets each reviewer address the remaining engineering disagreement.

SemIf may suggest that two findings are duplicates, but both original findings remain available. Only authenticated participant turns and the deterministic same-digest gate can close a material objection and establish convergence. It cannot declare that the debate is over, suppress a dissenting objection, or rewrite either model's contribution.

**Acceptance:** less duplicate review work with no lost blocking finding; conflicting, paraphrased and adversarially worded objections stay auditable. **Failure fallback:** pass all original objections to both reviewers.

### 6. Plan/local-implementation drift sensing

Compare a scoped diff against the approved invariant: “completion records remain durable across restart.” A change can be tiny in lines but material in behavior. SemIf suggests `preserves_intent`, `possible_material_change`, or `insufficient`.

The original local Codex session investigates. Mechanical compatibility changes remain locally actionable; architecture, security, data semantics and rollback changes return to the same Pro/Fable case. Git hashes catch changed bytes; this sensor proposes where those changes might matter semantically.

**Acceptance:** detect small semantic regressions and distinguish harmless path changes; no learned result bypasses local reconciliation or resets old approvals.

### 7. Approved playbooks with persistent goals

Pro and Fable can co-produce a bounded diagnostic playbook alongside a solution: objective, allowed observations, optional branch predicates, mandatory checks and exits. Ordinary software validates the structure and action registry. SemIf chooses only among the currently permitted diagnostic branches. A stable objective persists between event-triggered choices.

This adapts goal hierarchy to coding without copying a game-loop timer. No model wakes every 100 milliseconds, and Pro is not repeatedly called to rediscover an unchanged goal. New strategies, mutation scopes or missing branches require the appropriate reasoning/review lane. [S07, S09]

**Acceptance:** finite progress through known diagnostic cases; termination and pause behavior under contradictory observations; no action can appear through prompt injection. **Failure fallback:** ordinary coordinator workflow.

### 8. Local counterexample workshop

During an authorized foreground task, a local generative model proposes a few failure cases or test inputs in an isolated workspace. SemIf ranks novelty and relevance against the current objection. Deterministic execution decides whether the candidate actually fails; trusted specifications or reviewed oracles decide whether that failure is meaningful.

This is not speculative decoding and does not inherit distribution-preservation guarantees. Avoid multiple models editing the main worktree. Carry the best reproducible counterexample, not hundreds of speculative criticisms, into the next Pro turn.

**Acceptance:** more independently confirmed defects found per unit of compute than random/adversarial-test baselines; do not reward trivial crashes, invalid inputs or tests that redefine success.

### 9. Semantic event filtering

Emit decision events when a pass fails, evidence arrives, scope changes or a review turn completes. Use deterministic handling for exit codes, processes, quota errors and GPU utilization. SemIf can classify the meaning of new unstructured log snippets and whether the owner needs attention.

Debounce repeated events and cap work. A classifier cannot hide a required failure, pause or safety question from the owner. This is a user-enabled local process, not a promise that this chat will monitor anything after the response.

**Acceptance:** lower notification noise without losing known blockers; observable latency and dropped-event counts.

### 10. Learn specialist predicates from outcomes

Once one predicate has real volume and value, collect approved, scoped examples with independent labels: test outcomes, human corrections and verified factual checks. Keep model-suggested labels separate. A compact classifier or low-rank adaptation may later handle that family, leaving SemIf as the general fallback.

The appealing self-improvement loop is **observe -> label -> train offline -> evaluate on held-out projects/time -> propose promotion -> approve -> canary**. It is not “the models agree, so train on their consensus and auto-deploy.” An early proposal describes distilling repeated generic-classifier calls into specialists; it supplies motivation rather than measured results. [S12]

**Acceptance:** better speed/resource use at a predeclared error tolerance on held-out deployment-like data, no cross-project leakage, tested rollback. No training or policy modification runs by default.

## What not to build

Do not add a model to count files, check exit status, verify hashes, measure memory, or infer repository permissions. Do not implement an AI-only security firewall, high-confidence auto-deploy, or semantic replay of privileged actions. Do not treat equal model opinions as independent evidence, multiply correlated question scores into a fake success probability, or assume all choices share a calibration curve.

An external security-design paper shows the value of explicit control/data separation and capability enforcement. AgenticArch borrows the principle, not that paper's security guarantee. The classifier remains fallible and untrusted as an authority source. [S13]

## Selection

Build the **bounded, event-driven decision plane** in `DECISION-PLANE.md`, initially with context selection, requirement gaps, next diagnostics, drift, and debate triage in shadow mode. Add memory after provenance and invalidation work. Add playbooks and local counterexample generation after the core workflow passes. Attempt specialist training only when collected outcomes justify it.

The richer local layer does not replace the owner model policy, deep-review loop or original local Codex session. It reduces the work those components waste and improves the evidence they receive. Validate that hypothesis using `DECISION-EVALUATION.md`, not a token-cost story.

See [primary sources and limitations](RESEARCH-SOURCES.md).
