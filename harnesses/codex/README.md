# Custom Codex profile

This package is the primary workstation integration target, not a prebuilt replacement Codex. It shares `../../config/model-routing.json`, the CLM adapter, effort gate, review protocol and skills with Pi. Read [the main architecture](../../docs/ARCHITECTURE.md).

## Execution

Keep the existing client and authentication intact. Use qualified Codex ChatGPT-login workers for Luna/Astra, the user's unmodified Claude Code worker for Opus/Fable, and manual Pro web handoff. `profile.json` disallows API fallback. Observe actual billing mode, model, effort and quota before dispatch; a saved API key is not permission to use it.

Integrate an Astra-Ares-style native checkpoint immediately before sampling, after new user input and tool results are recorded. Port to the exact installed fork rather than applying an arbitrary upstream patch to a different revision. The local evaluator is CLM, never the upstream paid cloud evaluator. It receives the compact, exact-tokenizer-checked context and restricted effort/lease options.

The host holds its sampling/settings lock, calls `checkpoint_adapter.apply_checkpoint`, captures effective settings, and then calls `EffortGate.begin`. Only a matching acknowledgment permits sampling. Report APPLIED only after capture, never when a choice arrives. `checkpoint_adapter.py` is a tested host contract; connecting it to the actual Rust/native checkpoint remains implementation work.

## Implementation order

Inventory the current fork, skill roots and working subscription paths read-only. Create a separate build/profile with a known rollback. Port the native checkpoint and cancellation semantics; use synthetic evaluator output first. Connect immutable local CLM in shadow mode, then evaluate. Preserve direct provider transport, native history and permission checks. Do not inject synthetic role messages to impersonate native configuration updates.

For Opus as a medium-tier peer, dispatch through the verified Claude Code bridge at an idle worker boundary. Do not patch Claude Code. If its installed interface lacks safe generation-level changes, hold the selected effort for that job and change only on a later job.

## Acceptance

Test pending/stale acknowledgments, manual override, concurrent input, failed tools, cancellation, resume, model fallback, quota exhaustion, compaction and cache observations. Verify no request occurs on a rejected checkpoint. Confirm real subscription counters and no API/overage use. The offline `tests/test_revision.py` checks the host contract, not those live properties.

Rollback stops new dispatch, cancels/checkpoints active work, restores the original client profile and invalidates leases. Preserve code, case records, owner edits and auth. Never overwrite a global Codex binary as an automatic recovery step.

Start implementation with [this entry point](IMPLEMENT.md).
