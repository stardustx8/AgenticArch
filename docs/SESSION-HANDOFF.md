# Current session handoff

Updated: 2026-09-24. Status: initial GitHub development baseline.

## Project purpose

Build an evidence-driven local orchestration layer around the owner's custom Codex, which can use local and remote models on the AI workstation. Keep the system small, preserve existing integrations and use SemIf for bounded decision support beyond model routing. This repository contains the full reusable implementation context; no preceding chat is required to understand its requirements or plan.

## Non-negotiable owner choices

Luna uses low/high only. Medium-tough work uses Astra high. Tough work, architecture and research use GPT-6 Pro in ChatGPT web through `prepare-sol-pro-architecture-review`. After Pro's durable initial contribution, `fable-adversarial-review` coordinates actual Pro/Fable challenge through `GPT-Pro-Escalation`. Every Pro continuation uses the same case chat. Both participants approve the same solution digest; the original local Codex session then implements with explicit local-context reconciliation. See [R01–R23](OWNER-REQUIREMENTS.md) for the complete requirements and acceptance mapping.

## What exists now

The initial kit contains normative documentation, a four-lane policy, nine shadow-mode semantic operators, JSON schemas, synthetic examples, pure Python reference helpers, case/review templates, a master implementation prompt and both directly revised skill trees with an installer. Publication adds this handoff, a repository entry point and a durable decision log. The earlier local archive/bundle is a historical transfer copy; future work should start from the latest GitHub checkout.

Both skill definitions are supplied under their exact names. They have not been installed into the owner's actual custom Codex, and any additional local helpers have not been inspected.

## Verified and unverified

Offline checks rerun during publication preparation on Linux / Python 3.13.5: **93 unit tests passed**, kit checks passed, and the synthetic decision-plane demo passed. The original 66-file source ZIP and local bundle were byte-for-byte consistent before adding the GitHub handoff. Remote publication must be verified against the branch/tree actually returned by GitHub; do not infer it from a local artifact.

Live Codex dispatch, installed SemIf inference/calibration, real Pro/Fable conversations, runtime state/recovery, local skill migration, target-project tests and end-to-end implementation remain **NOT_RUN**. No independent Pro/Fable review of this kit has been performed. No CI workflow has been configured by this publication.

## Open gates

The kit records an unresolved capability/permission gate for automatic ChatGPT web operation and defaults to the manual ZIP/prompt route. Preserve that gate and its dated primary-source references; do not treat a custom client as proof of permission or silently substitute an API model. Revalidate the cited official guidance before attempting to qualify a future transport.

The separate `GPT-Pro-Escalation` runtime repository has not been created or provisioned by this publication. Use the supplied template only after resolving its exact owner, visibility and access within authorization. No real review case or private context is published here.

Actual model identifiers, local paths, provider interfaces and installed helper behavior must be discovered privately on the workstation. No repository license has been selected. These are explicit remaining decisions, not reasons to delay already-specified mechanical work.

## Next session: concrete starting task

Read [the implementation prompt](../prompts/IMPLEMENT-AGENTICARCH.md) and the linked specifications. Run the offline checks. Then execute Phase 0 of [the implementation plan](IMPLEMENTATION-PLAN.md): read-only inventory of the actual custom Codex, skill trees, SemIf, model bindings, Git access and working tree. Keep sensitive results private; commit only a sanitized capability/status summary.

After discovery, implement the specified Phase 1 local loop in small tested increments. Do not replace this handoff with another architecture essay. New consequential design decisions still go to the required Pro/Fable workflow, using the manual handoff while automated transport remains unqualified.

## Session closeout contract

Update this file, implementation status and any affected decisions together with code changes. State the task, branch, observed base revision, changed components, exact commands/results, live-versus-mock evidence, remaining gates and next concrete action. Never claim a running background job or a completed remote operation without its verified state. Preserve concurrent session work and refresh the remote before integration.
