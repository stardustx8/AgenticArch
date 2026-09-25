# Harness decision and subscription constraints

## Decision

Maintain both packages on `main`, sharing the same core. Start integration with the existing custom Codex to preserve working state, auth and tools. Keep Pi as a serious alternative, evaluated on the owner's tasks rather than selected solely from a social claim. No API-credit execution or paid overflow is an implicit fallback.

[HarnessTax](https://arena.ai/blog/coding-agents-harness-tax) supports testing lean harnesses, but not universal zero-loss savings. Its small sampled benchmark experiment prices tokens with an API rate card. It measures neither this project's new model versions nor subscription allowance. The exact relevant observations and limitations are recorded once in [the evidence registry](../config/research-evidence.json).

The owner's quota correction is incorporated: unnecessary model work can reduce included coding capacity. [Codex guidance](https://developers.openai.com/codex/pricing/) explicitly recommends reducing prompts and tool context to extend usage. Nevertheless, quota can use provider-specific weights, windows or message counters. Cache reads, output, reasoning, retries and plan rules complicate the relationship. Optimize measured allowance, not an assumed API-dollar conversion.

## Three configurations that must not be conflated

**Custom Codex + Claude Code workers:** the existing Codex path handles OpenAI work, with a generation checkpoint where supported. Claude work runs through the user's unmodified, authenticated Claude Code. This preserves familiar tool control and subscription behavior, but entails patch maintenance for native effort adaptation.

**Pi with delegated subscription workers:** Pi coordinates the same Codex and Claude Code workers and local CLM. This is a complete subscription-oriented architecture, but the workers retain their own prompts/tool scaffolding. There is no native-Pi savings claim. The coordinator itself should be deterministic or use a qualified subscription/local model, never an extra API-funded reasoning loop.

**Native Pi model execution:** qualify provider by provider. A verified OpenAI subscription path may be enabled after checking terms, actual account mode, effective identity, limits and cancellation. Technical OAuth availability is not sufficient. Do not move Claude subscription credentials into Pi's provider layer. The supported Claude branch remains an unmodified Claude Code worker signed in through its own flow; see [Anthropic's credential guidance](https://code.claude.com/docs/en/legal-and-compliance).

No configuration changes plan entitlements or bypasses account enforcement. A native route that cannot meet the subscription requirement stays disabled; the delegated profile remains usable.

## Controlled comparison

Use matched tasks, isolated worktrees, fixed model/effort, equivalent permissions and acceptance tests. Alternate run order. Record full success and failures, retries, elapsed time, human interventions and attributable quota deltas for each provider bucket. Track input, cached input and output as diagnostics, not replacement quota measurements. Control concurrent use across devices or mark attribution unavailable.

Keep security/approval capability parity. Removing protections is not an acceptable harness optimization. Compare native Pi only against native peers; compare delegated Pi as a distinct orchestration configuration. Select a deployment after task-level quality and recovery pass, then use quota and latency to choose among acceptable systems. See [the evaluation protocol](SUBSCRIPTION-EVALUATION.md).
