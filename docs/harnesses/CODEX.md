# Codex profile

This is a complete profile of the shared architecture, not a second policy. Read the root agent instructions, CLM adapter, routing policy, review protocol and implementation plan. The primary environment is Linux with the owner's custom Codex and local GPU.

## Execution path

Use the existing authenticated Codex worker for OpenAI subscription work. Preserve native approvals, tools, cancellation, transcript and direct provider connection. Invoke Claude through its unmodified, user-authenticated Claude Code worker for the selected exact model. The controller never copies subscription credentials. No paid API fallback is enabled. Verify effective billing mode, because an inherited API key or third-party proxy can change the path.

Use one local controller with persistent task state and a private outbox. CLM supplies bounded advice; deterministic policy decides what is eligible. The original task/session owns implementation, and the existing Pro ZIP/manual-chat protocol owns deep review. Native integration, local safety and recovery gates apply regardless of the model selected.

## Astra-Ares adaptation

Use [Astra-Ares's documented checkpoint](https://github.com/miuuyy/Astra-Ares/blob/main/docs/architecture.md) as the integration pattern. Inspect and pin the actual custom Codex source before porting any patch. Do not replace the owner's binary with an untested upstream build. Add a pre-generation checkpoint after accepted inputs and available tool results are in history. Send a bounded public evidence projection to local CLM, not hidden reasoning.

Validate the proposed effort against the selected model's small allowed menu and current step floor. Apply through the native settings owner, capture the next generation's effective model/effort, then acknowledge. A request or UI label alone is not APPLIED. Maintain one settings owner and count leases in generations, including the next generation. Lease values are 1, 2, 5 or 10; uncertainty favors a short lease or abstention, not an invented effort.

Invalidate after new user input, tool failure, changed task or policy, manual effort selection, model switch, compaction, cancellation, or changed capability. Preserve manual selection until the user clears the override. The model stays fixed within an effort lease. A model switch happens through a separate safe task handoff.

GPT-6 prefix-preserving configuration updates are a capability to verify, not a universal cache promise. Test continuation, compaction, reconnect and restart. If the client cannot expose the exact next-generation setting, disable dynamic changes and use a verified fixed allowed effort; record the limitation.

## Qualification and rollback

First perform read-only discovery of source revision, installed helpers, active authentication, effort controls and quota surfaces. Test with synthetic inputs and a fake CLM response, then opt-in live fixtures. Compare against fixed Luna high and Astra high. Preserve baseline worker paths and private settings backups. Roll back by disabling the checkpoint adapter, not by weakening approvals or changing auth. This repository has not installed or live-qualified this profile.
