# Subscription-aware evaluation

The primary resource is useful verified work within each finite subscription allowance. API-equivalent dollars, tokens, latency and GPU time are diagnostic measurements, not substitutes for observed allowance. [Codex documents](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan) that context and reasoning affect usage. The owner's concern therefore matters even without pay-per-token billing.

## Observation record

For each run record task family, anonymized project/snapshot, requirements and check-plan hashes; exact model revision, requested/effective effort and harness version; native/delegated path and authenticated billing mode; start/end quota observations for each applicable short and long window; reset times, sampling precision, concurrent consumption, latency, retries, cache reads/writes, reasoning/output tokens when exposed, actual checks and final outcome.

A missing counter is null, never zero. A reset, changed plan, concurrent unrelated usage or insufficient dashboard precision makes the task-level quota estimate inconclusive. Batch repeated matched tasks within one unchanged window where necessary. Keep OpenAI and Claude pools separate; do not add fractions of different allowances as if they were interchangeable currency. Preserve shared-pool overlap rather than double-counting it.

## Experiment design

Use the same task inputs and acceptance contract across profiles. Randomize or counterbalance order, isolate working trees, account for cache warmup, repeat tasks and split evaluation by project/time to limit memorization. Predeclare quality tolerance, decision confidence and budget. Include failures, retries, review and final verification in consumed work. Native Pi, Pi delegation and custom Codex are three treatments, not two interchangeable labels.

Compute quota used per verified completion only within a comparable pool/window/protocol. Also report absolute completion rate and its uncertainty; a cheap failure is not a productivity gain. Unknown usage or insufficient quality evidence blocks automatic promotion. Compare both fixed and adaptive efforts. Keep holdout tasks untouched while tuning CLM heads or route descriptions.

## Operational policy

Prefer a qualified Pareto-efficient candidate meeting quality, safety and latency requirements, rather than minimizing a synthetic weighted score by default. When evidence cannot discriminate Astra high and Opus medium/high, preserve the configured baseline or request an explicitly scoped pilot. Do not invent precision through CLM probabilities.

Monitor quota pressure with native status surfaces and honor reset times. Exhaustion pauses, or selects another already-authorized qualified peer; it never purchases credits, changes account or falls back to API billing. Startup context trimming, caching, scoped retrieval and reduced rework are separate interventions. [Owens's first-hand measurements](https://joshowens.dev/the-harness-tax/) illustrate why a short-call saving should not be extrapolated to a long replay-heavy workflow.

Local energy and memory also matter: keep CLM warm where useful, reuse action embeddings, limit heavy concurrent candidate generators, and measure head fine-tuning separately. Subscription optimization does not justify deleting relevant requirements, tests, approvals or recovery state.
