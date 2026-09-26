# Pi profile

Pi and Codex share the same requirements, CLM service, decision catalog, evidence store, review protocol and tests. Do not fork the whole specification. The Pi profile is a viable coordinator alternative, with native minimal-model execution separately qualified.

## Two different modes

**Subscription-worker mode:** Pi coordinates local tools and invokes native Codex and unmodified Claude Code workers, each using the owner's own normal sign-in. It may use a qualified local coordinator model; no API spend is implicit. This mode preserves native worker overhead. Do not claim native-Pi benchmark savings merely because Pi launched the worker.

**Native-model mode:** Pi owns the model/tool loop. OpenAI subscription use is conditional on an explicitly supported, permitted authentication flow and observed subscription billing. An OAuth implementation or successful HTTP call alone is not sufficient evidence. Until qualified, delegate to native Codex. Direct Claude subscription-token reuse is disabled. [Anthropic's guidance](https://code.claude.com/docs/en/legal-and-compliance) distinguishes native user sign-in to the unmodified binary from third-party credential intermediation. Keep Claude Code as the subscription worker; never extract its tokens or remove its authentication methods.

Both modes prohibit silent paid API fallback, subscription pooling across users and bypassing provider limitations. Stop or choose another already-authorized eligible route when quota is exhausted. Do not purchase credits or use fast/overage modes automatically.

## Extension design

Implement a thin TypeScript extension using the installed version's actual [ExtensionAPI](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/extensions/types.ts). Pin the package and test its declared lifecycle. Observe accepted input, tool results and safe turn boundaries. Keep controller state outside model-visible text, using durable entries only for sanitized bindings. Do not add a second generative supervisor for every small decision.

At the next safe generation boundary, call the shared CLM decision compiler and deterministic effort guard. Use Pi's model/thinking controls only when qualified for that exact provider. `setThinkingLevel` may clamp: read back the actual setting and verify the provider request mapping. Preserve provider-specific reasoning state and never re-label one model's private thinking as another's. For delegated workers, apply effort through the worker adapter, not Pi's own thinking selector.

Register optional tools but expose only those necessary for the current task. This is a context-efficiency tactic, not an OS sandbox. Extensions execute with process privileges, so run untrusted projects under the same reviewed isolation and file/network restrictions as Codex. Batch-safe tool behavior, cancellation, outbox reconciliation and private credential storage are required.

## Workstation rollout

Discover installed Pi package identity, extension types, available providers, native worker command schemas and sign-in state. Begin with subscription-worker mode and synthetic extension events. Run the shared acceptance suite for restarts, duplicate events, manual override, clamp mismatch, missing head, failed test and quota exhaustion. Pilot native OpenAI mode only after its separate permission/capability gate passes. Compare complete tasks, not first-call tokens.

A Pi session may resume a task from Git context, but it may not seize an active coordinator lease or change the case's Pro chat. Switching harnesses requires a recorded ownership transfer with no running tools and the same pinned approved result. Rollback disables the extension and resumes the existing Codex profile. No Pi package has been installed by this kit.
