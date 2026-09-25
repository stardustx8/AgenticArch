# Concurrent-session integration record

2026-09-25. The prepared full revision began at 8b96744. While it was being tested, main advanced through 29f554b, f3538855, 10592526 and 294ebcb0. The integration preserves all four commits as ancestors and retains their additional source, tests and research. No forced update or historical rewrite is used.

## Canonical and supplemental records

The executable routing catalog is `config/model-routing.json`; its S-number evidence IDs resolve through `config/research-evidence.json`. The independently published `config/evidence-registry.json` and `docs/MODEL-AND-HARNESS-RESEARCH.md` are preserved as supplemental authored research, including additional editorial experiments. Their descriptive IDs are a separate namespace and are not automatically equivalent to S-number IDs or local qualification evidence. New decisions should link the correct registry explicitly.

The active harness packages are under `harnesses/codex/` and `harnesses/pi/`. The retained `config/harness-profiles.json` and `docs/harnesses/` are compatible high-level profiles from the concurrent session, not a second runtime implementation. Their `native_codex_subscription` and `native_claude_code_subscription` labels describe the corresponding `codex_subscription` and `claude_code_subscription` methods in the active catalog. Do not create another dispatcher from naming differences. Both records prohibit paid fallback and direct Claude subscription-token intermediation.

`docs/SUBSCRIPTION-EVALUATION.md` is the active measurement contract; `docs/QUOTA-EVALUATION.md` retains additional evaluation guidance. Both require separate provider pools, honest precision and verified quality. No measurement of actual savings is implied by merging them.

## Source compatibility and host events

The concurrently published CLM interface and 13 tests remain intact. Generic prepared-choice callers keep their import path through compatibility exports. New model-routing callers use the deployment-supervised client. Live attestation must not be bypassed through the compatibility transport. The current reference suite has 189 passing Python tests.

Host-specific compaction, cancellation and capability-change events invalidate the active lease. Map them explicitly to the existing scope-change, resume or policy/deployment invalidation as appropriate after an in-flight generation settles. Do not pass an unknown event into the strict reference gate or claim that catching its error safely authorizes another request.

Revision-local requirement IDs from the concurrent work are mapped in REVISION-2026-09-25.md to the canonical owner requirements; overlapping numbers are not silently reinterpreted. Future sessions should read the current handoff and this record before consolidating duplicated explanatory material.

## Concurrent routing compiler retained

Commit 294ebcb0 added a v1 catalog, route/effort compiler and 25 tests. Preserve the catalog byte-for-byte under `config/compat/model-routing-v1.json` and the implementation byte-for-byte in `reference/routing_compat.py`. Its public names remain available from `reference.routing`; only its test fixture path changes, leaving every test assertion intact. The active v2 implementation is isolated in `reference/routing_v2.py` and accepts only its own schema. The public catalog validator dispatches by explicit schema version rather than merging policies.

The v1 and v2 CLM envelopes, model-family aliases, transport names and generation-index conventions are deliberately not mixed. All active runtime profiles point to v2. The retained compiler is compatibility/research evidence, not a parallel live dispatcher. Consolidation can occur later through an explicit tested migration, not deletion of another session's contributions. A temporary cooperative integration notice is removed by the final commit.
