# Integration reconciliation, 25 September 2026

This note reconciles PR #1 (`integration/clm-participant-policy-20260925`, head `b66a5e1`) with `main` at `dd426bc`. Both lines forked at `294ebcb`, and both implemented the same participant contract in parallel. The merge keeps both lines' commits in history.

## Decision

The 15 files that both lines changed keep **`main`'s version**. `main` is the later, complete integration of the same contract: its code, schemas, skills, prompts and 189 tests all use one vocabulary. Mixing in the PR's parallel names would have split that vocabulary. PR #1's guarantees are all present in `main` under these names:

| PR #1 | `main` |
|---|---|
| `debate.required_roles = [pro, reviewer]` | `[pro, claude]` |
| `debate.reviewer_identities` | `debate.claude_models` (same two identities) |
| `debate.participant_bound_approvals` | `debate.participant_change_invalidates_approvals` |
| `subscription_only`, `api_fallback: false` | `billing.remote_mode = subscription_only`, `billing.api_fallback = false` |
| `Receipt.participant_identity` | `Receipt.model_id` (observed identity) |
| `CaseReview.reviewer_identity` | `CaseReview.claude_model_id` (frozen per epoch) |
| `participant_binding_digest` (a new session binding voids approvals) | `review_epoch`: an identity or configuration change starts a new epoch, and earlier turns cannot approve it (`docs/ESCALATION-PROTOCOL.md`, `docs/STATE-MACHINE.md`) |
| error `invalid_participant_binding` | `invalid_claude_participant`, `participant_model_mismatch` |
| phase `reviewer_challenge` | `claude_challenge` |

## What PR #1 adds to `main`

- `tests/test_participants.py`: PR #1's five participant regressions, ported to `main`'s API. They cover Opus as an equal partner, a partner switch, a new binding (as a new epoch), a missing identity and the unreleased successor. One extra check, that a receipt from another model does not count, was added. All pass, which confirms `main` enforces each guarantee.
- `tests/test_regressions.py`: PR #1's two score-validation regressions (bad sum, unknown choice), unchanged.
- `docs/PARTICIPANT-POLICY-HANDOFF.md`: PR #1's handoff, kept as history.

## Verification

- `python3 -m unittest discover -s tests`: **197 tests pass**, the 189 from `main` plus 8 from PR #1. On macOS, run it with a non-symlinked temp folder: `TMPDIR=$(cd "$TMPDIR" && pwd -P)`. The installer deliberately rejects symlinked paths, and `/var` is a symlink there.
- `tools/check_kit.py`, `tools/demo_decision_plane.py` and both `tools/preview_routing.py` harness previews pass.
- Offline checks only. There was no live model, harness or workstation test.
