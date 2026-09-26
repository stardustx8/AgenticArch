# Pi profile

This is a complete alternative architecture package sharing AgenticArch's core, not a claim that Pi can use every provider's subscription directly. Begin with [the harness decision](../../docs/HARNESS-DECISION.md) and `profile.json`.

## Subscription-oriented design

Run a local deterministic coordinator and CLM. OpenAI work can use a qualified native Pi subscription route only after its permission, account/billing mode, model and quota behavior are verified. Otherwise delegate to a Codex subscription worker. Claude work uses the unmodified Claude Code worker through its own user authentication. Pro remains in its case-bound web conversation. Do not put Claude OAuth/session tokens into a Pi custom provider.

Delegation retains the worker's internal harness overhead. Do not claim native-Pi benchmark savings for delegated execution. Pi's own planning calls must use a qualified subscription or local model, never an unannounced API bill. Protect the process with a real OS/workspace sandbox: a four-tool interface containing bash is not itself a sandbox.

## Adaptive effort

`effort-adapter.ts` implements the observed Pi thinking setter/readback/abort contract and an awaited `turn_start` binding. Supply `observe()` from trusted native state and `decide()` from the bounded local coordinator, using `reference/effort.py` for lease/epoch handling. The observation must carry real session, model, generation and qualification facts. The decision source must have a timeout and cancellation. It must never copy hidden reasoning or credentials into CLM state.

A stale decision, changed context, unsupported/clamped setting or cancellation calls `ctx.abort()` and rejects the generation. Real Pi/provider acceptance must prove that abort prevents the outgoing request; the structural fixture does not establish that. A production plugin must also integrate all lease invalidators and acknowledge each generation's observed settings to the coordinator.

Model switching happens at a worker boundary, with an explicit model/capability/billing check and a new lease epoch. Keep public evidence, not incompatible provider thinking blocks, when creating a new worker context. Native cache behavior and long-session compaction require tests. Delegated workers use their own checkpoint surfaces, not Pi's thinking setter.

## Offline check

With Node.js and TypeScript already installed:

```sh
tmp="$(mktemp -d)"
tsc --strict --target ES2022 --module commonjs --outDir "$tmp" harnesses/pi/effort-adapter.ts
node harnesses/pi/test-effort.cjs "$tmp/effort-adapter.js"
```

Run from the repository root. No model call or package installation occurs. The adapter uses structural interfaces to avoid claiming compatibility with an uninstalled package; compile and test against the pinned actual Pi package during local qualification.

## Implementation and rollback

Discover the actual Pi version and extension contracts, preserve existing profiles, and load the trusted extension only in a dedicated project profile. Bind the shared private state/outbox and worker adapters. Test tool permissions, cancellation, resume, billing denial, session replacement, clamp/fallback and concurrent edits before enabling advisory CLM decisions.

Disable the extension/profile to restore fixed-effort workers, invalidate all leases and retain private state for recovery. No deletion of shared skills or credential stores. Start with [IMPLEMENT.md](IMPLEMENT.md).
