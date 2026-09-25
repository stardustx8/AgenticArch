# Dynamic reasoning without unbounded effort menus

## Two different decisions

Task routing selects an eligible model and harness at a worker boundary. Effort routing selects a setting for the **next generation of that fixed model**. It does not interrupt an ongoing generation, change Pro's identity, or weaken the task's architecture/research requirement.

The task's policy tier remains fixed or escalates. A next-step minimum may vary within an approved plan: a narrow mechanical step can need less deliberation than interpreting a concurrency failure. Only explicitly permitted per-model efforts enter that checkpoint's menu. Unknown next-step requirements keep the default rather than silently authorizing less reasoning.

## Permitted menus

Luna: low/high; substantive default high. Astra: high. Opus 5.5: medium/high, deep-review minimum high. Fable 5.1: high. GPT-6 Pro web has no fabricated API effort knob. Fable 5.5 is disabled.

CLM chooses among joint options such as `high_for_2` rather than two inconsistent decisions about effort and duration. Allowed leases are 1, 2, 5 or 10 **generations**, including the upcoming generation. One generation may issue several tools. A singleton effort menu still allows a lease choice, although deterministic reuse may make a model call unnecessary.

The catalog contains the description template and invalidators; `reference/effort.py` enforces one pending decision, bounded duration, exact session/model/epoch matching, readback and dispatch blocking. It is host-independent, not proof the host has a native checkpoint.

## Astra-Ares adaptation

The [upstream architecture](https://github.com/miuuyy/Astra-Ares/blob/main/docs/architecture.md) applies native settings, captures a new step context, verifies it and acknowledges before sampling. Preserve that ordering. Replace only the cloud evaluator with the local CLM choice adapter and this project's constrained menu. Keep authentication, tool permissions, cancellation and history native. A shell wrapper or MCP prompt alone is not an equivalent pre-generation hook.

Its 28,000-token evaluator view must not be copied into a 2048-token CLM deployment. Build an explicit evidence projection that preserves constraints and unknowns, then exact-tokenizer check it. Oversize or unavailable CLM means a recorded policy-default decision or pause, not concealed truncation or paid fallback.

## Pi adaptation

The [Pi package](../harnesses/pi/README.md) supplies an adapter for the verified thinking setter/readback/abort surfaces. Bind it only at an awaited pre-generation boundary. Extension errors alone may not stop Pi; the integration must honor explicit abort and prove that no provider request escaped. A setting clamp is an error, not successful application. Native provider prefix preservation must be tested; a setter's presence does not prove cache behavior.

Pi delegating to Codex uses the Codex worker's native checkpoint, not Pi's local thinking setter. Claude worker effort changes require a verified native surface; otherwise keep effort fixed for the current worker and change it only when starting the next authorized worker. Do not patch the Claude Code binary or rewrite private thinking blocks.

## Invalidation and recovery

New user input, tool failure, model switch, manual override, changed scope/policy/deployment or session resume ends the lease. Manual choice wins until explicitly released. Failures trigger reassessment, not automatic max effort. In-flight cancellation must be acknowledged before the next decision. Restore case/session context after restart, but never restore an active lease without revalidation.

Native GPT-6 configuration updates can preserve the original prefix under their supported lifecycle. [The official guide](https://developers.openai.com/api/docs/guides/reasoning#change-reasoning-mid-conversation) does not guarantee a particular cache hit rate. Test compaction, truncation, resume and provider switches separately. Record requested versus applied effort, generations, invalidators, latency, cache observations and quota, never hidden chain-of-thought.
