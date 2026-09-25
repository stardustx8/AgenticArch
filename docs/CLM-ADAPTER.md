# Local Contrastive Language Model adapter

Status: reference client and offline contract tests implemented; workstation deployment and workload qualification not run. This is the replacement decision backend, not a coding model or policy authority.

## Upstream contract and pins

The implementation was checked on 2026-09-25 against [CLM commit bb42c6c](https://github.com/Contrastive-LM/CLM/tree/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7), particularly [the schema](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/src/clm/schema.py), [client](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/src/clm/client.py), and [README](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/README.md). Pin the serving package, encoder, tokenizer, pooling method and projection-head checksum together. A head is not interchangeable with an arbitrary encoder. The small head download is not the memory footprint of the complete encoder.

CLM scores state/action compatibility using separately encoded texts and learned projections. The maintained policy is JSON; the actual state and option representations should be concise prose. Upstream puts context first and the question last. A `choice` candidate is its description alone, so every option must be self-contained. Do not encode a rule exclusively in its opaque option ID. Do not duplicate the question in the state or send the entire research registry with every decision.

## Wire format

`POST /v1/systemone` accepts `model`, `state`, and a map of typed `questions`. AgenticArch initially uses `choice`, not numerical `score`, to choose a bounded route or effort. Each question has `type: choice`, `instructions`, and `criteria: {option_id: prose_description}`. Every decision includes `insufficient`. Noul and score may be added for separately qualified operators; they are not substitutes for deterministic arithmetic or permissions.

The reply contains `model` and `answers`; each choice answer contains `type`, `choice`, `probabilities`, and `confidence`. The upstream confidence field is the top probability minus the mean of the remaining probabilities. It is not a calibrated probability of task success. The reference adapter recomputes this separation and returns only advisory output. Ties and insufficient evidence abstain. NaN, boolean probabilities, mismatched options/model/question, modified requests, malformed output and timeouts cannot authorize action.

See [the reference client](../reference/clm.py) and [its tests](../tests/test_clm.py). The HTTP transport permits only a literal loopback address and port, disables environment proxies and redirects, and bounds request/response size and timeout. Errors do not expose private state or credentials. Production supervision must verify that the local service is the pinned deployment; the response's model string alone is not attestation.

## Token limits and caching

Upstream defaults to a 2048-token encoder limit and truncates longer states. That is unsafe for routing when a requirement disappears. Count the exact rendered state-plus-question and each candidate with the deployed tokenizer, including its special-token behavior, before sending. Raise both encoder and CLM limits together only after memory and quality tests. A character or whitespace counter is acceptable only in explicitly synthetic tests. On overflow, reduce the evidence projection without dropping mandatory facts, split the question, or abstain; never silently truncate.

Cache reusable action descriptions independently. The state representation includes the question, so different questions need not reuse the same state embedding. Separate raw-embedding and projected-vector cache identities. Bind cache entries to tenant/project scope, exact text, encoder/tokenizer/pooling, head generation, renderer, quantization and any calibration. A changed head invalidates projected scores and previous qualification; upstream hot reload must be disabled operationally or detected before accepting results. Never reuse a decision after requirements, authorization, snapshot or candidate set changes.

## Workstation deployment contract

Run the encoder and CLM service locally, bound to loopback, with a private local key where supported. Keep the playground and cross-origin access off for unattended use. Pin dependencies and checkpoint provenance before loading weights. Inspect the actual GPU memory needs and reserve capacity for existing workloads rather than assuming the workstation can host every optional model concurrently. Keep tokens, endpoint details and real evidence out of Git.

The documented upstream pattern is a Qwen3-8B pooling encoder with the matching released head. This kit does not install it or download weights. The local agent must validate service health, selected head, tokenizer counting, non-truncation, cancellation, timeout, reload behavior and real fixtures on the owner's hardware.

## Evaluation and migration

Start in shadow mode. Use the existing context-relevance, evidence-gap, next-diagnostic, local-drift, memory and review-triage operators, but re-evaluate each on CLM. Old-backend scores and calibrations do not transfer. Model/effort routing adds its own qualification set. Compare against deterministic rules, retrieval baselines and a small trained classifier when the task is repetitive; CLM is not mandatory where ordinary code is adequate.

Use task/project/time-disjoint evaluation, option-order perturbations, negation and missing-information cases, false-safe rates, abstention/coverage, latency and downstream verified completion. Fine-tune heads only on provenance-tracked outcomes with held-out tasks. Keep a rollback head and separate candidate generation cost from verifier selection cost. Upstream best-of-N agentic results use small held-out subsets and multiple candidate solutions, not single-run full-benchmark performance; do not relabel them as general correctness guarantees.

The deterministic coordinator still enforces scope, model floors, subscription access, verification and exact-version review consensus. CLM never grants permissions, submits external work, runs a shell command, lowers a mandatory review requirement or declares completion.
