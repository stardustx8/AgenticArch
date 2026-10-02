# Local CLM adapter

## Pinned implementation and representation

The implementation reference is [CLM at bb42c6c](https://github.com/Contrastive-LM/CLM/tree/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7). This is a contrastive state/action encoder design, not the previous backend under a different name. Reset old scores, calibration and caches. Pin backbone, tokenizer, pooling, projection-head checksum, runtime, rendering and catalog versions together.

Store maintained knowledge in `config/model-routing.json`. Render task context as compact prose and each permitted action as a short distinct description. Put the question after context. The wire request is `POST /v1/systemone` with `state`, `model`, and a `questions` dictionary containing typed `choice` questions and `criteria` maps. The upstream schema renders objects to prose. Do not send the entire research registry to an encoder trained to compare state/action text.

`reference/clm.py` implements the actual HTTP shape, strict response validation, bounded body size, no redirects/proxies, loopback-IP-only transport, tokenizer preflight and deployment checks around scoring. Its `Choice` is a validated wire result; `schemas/clm-advice.schema.json` remains the separate normalized AgenticArch envelope. Never pretend one is the other's upstream schema.

## Deployment contract

The supervised deployment must bind both servers to loopback. The upstream CLM server defaults to all interfaces, so explicitly set `--host 127.0.0.1`, a reviewed checkpoint, `--no-download` and `--no-ui`. Leave CORS disabled. Configure the embedding server independently with loopback binding and a matching token limit. Keep authentication in a private environment or secret store.

Start at the pinned 2048-token limit only with exact tokenizer preflight. Upstream truncates longer inputs: count the final context-plus-question and every action description, and reject overflow. Raising the limit requires raising both services' limits and testing memory. No silent truncation of requirements, constraints or failure evidence.

A trusted local supervisor supplies `deployment_digest()` and the exact tokenizer callback. The digest binds the reviewed head, encoder/tokenizer, pooling, server limits and configuration. The client cannot authenticate those facts from an untrusted boolean or the alias `clm-latest`. Run immutable checkpoint copies with no in-place hot reload; an upgrade restarts the process, increments deployment identity and invalidates in-flight scores. Verify health, including that a mock server is not active.

## Scoring and failure behavior

The returned probability distribution is conditional on the supplied action texts. Upstream confidence measures separation from other options, not correctness likelihood. Preserve this distinction. Ties, abstention, missing evidence and unqualified workloads return to the coordinator. A scored route must still pass current permission, model, billing and task-floor checks.

Measure cold/warm encoder work separately from cached action vectors. Vector reuse is not generative prompt-prefix caching. Cache identity must include exact action/state text and the full deployment generation. The controller also binds advice to project, task, snapshot, policy and authorization scope even when the numerical vector could be reused.

Timeout, invalid JSON, mismatched options/model, oversized response, changed deployment, OOM or missing weights makes CLM unavailable. Do not download, retry indefinitely, kill another GPU workload or call a remote endpoint as recovery. Keep deterministic fallback and an explicit diagnostic.

## Qualification

All operators start in shadow mode. Evaluate per task family on project/time-disjoint examples, including failures and abstentions. Compare context selection and diagnostics with existing search/rules. Train or calibrate only against independently verified outcomes. The upstream small held-out verifier experiments do not validate routing on this workstation. See [evaluation](DECISION-EVALUATION.md).

## Compatible generic-choice interface

The concurrently published generic-choice API remains import-compatible: `LocalCLM`, `PreparedChoice`, `prepare_choice`, `normalize_choice` and `render_state` are exported from `reference.clm`, with the unchanged implementation in `reference/clm_compat.py`. Its original 13 tests are retained in `tests/test_clm.py`. It supports named question IDs, a 16-option menu including `insufficient`, a byte-bounded prepared request and explicit deployment provenance. Its low-level transport leaves live service identity/freshness to the caller; it does not automatically gain the new client's before/after supervision. New routing uses `CLMClient`, the route question and `ABSTAIN`, not an unchecked conversion between the two envelopes.

Every candidate description must be self-contained; do not put a capability constraint only in an opaque ID. Exact tokenizer counting must include the deployed special-token behavior. Separate raw-embedding cache identity from projected-vector identity and retain quantization, renderer and calibration versions. A small projection-head download is not the complete encoder's memory footprint. Candidate generation cost and verifier selection cost remain separate. These requirements preserve the concurrent adapter's documented contract while adding the restricted routing/runtime gates.
