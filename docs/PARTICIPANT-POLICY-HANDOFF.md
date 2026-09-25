# Participant-policy integration handoff

Date: 2026-09-25. This handoff preserves a parallel session's completed work without replacing the active integrator's main branch.

## Durable work

This session published the requirement checkpoint `29f554b`, local CLM adapter/tests `f353885`, harness/research profiles `1059252`, and model-routing/effort compiler `294ebcb` on main. A subsequent policy/skill commit `c63192b` was retained on `integration/clm-participant-policy-20260925` after a non-fast-forward rejection. Main had advanced to `28adcbf` with an integration coordination notice. No force push or history replacement was attempted. Pull request #1 exposes the remaining work for reconciliation.

The branch's policy v2 and consensus kernel require logical `pro` / `reviewer` roles, exact selected Claude identity, participant-binding digests in transport receipts, and local task binding. Both exact-name skills and participant prompts follow this contract. Version-1 approvals cannot silently become valid version-2 approvals.

## Verification

Command: `python3 -m unittest discover -s tests -v` in the prepared Linux/Python working tree. Result: **138 tests passed**, including the 93 baseline tests, 13 CLM tests, 25 route/effort/quota tests, 5 selected-participant tests and 2 explicit score regressions. The prepared kernel blob `2a367be93673c20bb21e5a1cc89841a31ab07c6d` and main kernel-test blob `0ee19f44c3f891f999287755c06cabdb66a7657b` were independently read back from the branch and matched local bytes. This is offline verification, not live model or workstation acceptance.

The source references and model catalog are hypotheses with provenance, not local qualification. No live CLM GPU inference, native Pi subscription operation, Pro/Claude exchange, quota depletion measurement or installed skill migration occurred here.

## Remaining integration responsibilities

The active integrating session should reconcile this branch with its own solution instead of blindly replacing overlapping modules. Preserve exact selected-model binding, fail-closed quota/authentication checks, small effort menus and the original Pro transport boundary even if a different implementation is chosen. Repeat the entire test suite on the actual integrated tree.

The broad root documentation, state-machine/adapter references and normalized example filenames need to agree with the final selected backend, logical reviewer role and both harness profiles. Update `OWNER-REQUIREMENTS.md`, `SESSION-HANDOFF.md`, implementation status and the revision ledger together. CLM's own choice wire format must not be confused with the generic internal advice schema.

Do not claim subscription savings from the API benchmark; distinguish native Pi model loops from native-worker delegation. Do not activate Fable5.5 without release/access evidence. Direct Claude subscription-token reuse is not a permitted substitute for native Claude Code sign-in. A role string or model display name is not an actual transport receipt.

Once integration is complete, read back main and report the real commit. This document is a historical handoff; it is not a persistent lock or a claim that another session is still running.
