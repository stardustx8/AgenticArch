# Adapter contracts and trust boundaries

These are implementation contracts, not claims that these modules exist. Pin them to a schema version and test both successful and failed responses. All data from models, project files and web pages is untrusted until checked by the coordinator.

## Common job envelope

A dispatched job carries `schema_version`, unique `job_id`, `task_id`, optional `case_id`/`turn_id`, `input_snapshot_digest`, `requirements_digest`, `verification_plan_digest`, selected lane/role, allowed paths, working directory, permitted operations, deadline, cancellation handle and resource budget. Paths and permissions are supplied by trusted local configuration, not copied from model output. Secrets are inherited through the existing credential mechanism and never embedded in the envelope or command line.

A result records the original IDs/hashes, observed provider/model/version/effort, identity-evidence type, terminal status, artifact references, changed-file inventory, exact command evidence, usage when actually exposed, and transport receipts. Reject mismatched jobs, stale inputs and truncated/error responses. Missing usage remains unknown, not zero. A model-produced `identity_verified: true` is not an observation.

## Codex worker

Discover the custom fork's real provider registry, event protocol, session-resumption controls and sandbox capabilities. Prefer that integration over launching another framework. Dispatch an actual supported Luna low/high or Astra high configuration and verify effective selection from the transport. Context is scoped to the task/worktree. Preserve a stable original-task binding even when a worker session is restarted.

The adapter must reject provider incompatibilities, not silently erase required effort/tool parameters. Current [Luna documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) limits Chat Completions function calling to effort `none`. Since this policy allows only low/high, tool-using Luna dispatch must use an actually supported Responses/Codex interface. Revalidate when the provider changes.

## SemIf

Implement the normalized score interface in [the SemIf specification](SEMIF-ADAPTER.md). The local scorer receives declared ordered options and state; returns scores and provenance. No code edits, tools, permissions, remote fallback or completion authorization. Timeouts/schema failures degrade to policy-only routing. Raw options are not trusted as arbitrary controller commands.

## Pro web transport

Operations: `prepare`, `submit_first`, `submit_continuation`, `observe`, `collect`, `cancel_or_pause`, `reconcile`. The exact implemented set is capability-gated. Manual transfer implements preparation/checkpointing/collection without pretending to perform browser actions. Standard Computer Use cannot currently automate ChatGPT itself; see [the explicit gate](COMPUTER-USE-GATE.md).

Each send requires permitted capability, authorized export, expected case/turn, exact bytes and private chat binding. Reject a changed origin/account/model, missing binding on a continuation, or an uncertain previous send. No private chat URLs in shared case files. A human-attested selection is distinct from machine-observed metadata; store the evidence type. A returned answer is normalized only after required artifacts are actually available.

## Fable bridge

Load the installed `claude-code:use-claude-code` instructions and use its exposed schema. Resolve alias `fable` and supported high effort through that bridge. Read target source only within the approved evidence scope; guarded writes are limited to the review case. Resume the case-specific Fable session, not a global latest job. Poll foreground lifecycle or consume supported events; no silent abandoned job or forged independent review. An unavailable bridge blocks that participant.

## Git case transport

Acquire the one-coordinator lease, fetch the expected branch, verify the input commit and allowed changed paths, create a contribution on the expected parent, non-force push, read back exact bytes, then commit the receipt to local state. Native model writes and coordinator relays have separate provenance. Git committer identity is not a proof of the substantive model role.

Require content digests and path checks at both ingestion and publication. Refuse path traversal, symlinks, unexpected executable/config changes and writes outside the case. A case's approved artifact set is explicit. Extract archives into a bounded staging area with safe entry checks; never blindly unpack a model ZIP into a repository. Preserve append-only turn history. On conflict fetch/reconcile; do not overwrite or force-push.

## Evidence and resource adapters

The evidence runner executes approved argv arrays without a shell expansion of model text. Working directory, environment and timeout are controlled. Checks run against the recorded snapshot; detect file changes during the run. Capture stdout/stderr safely, keep logs private, label pre-existing failures and require explicit acceptance rather than silently ignoring them.

The resource adapter observes actual GPU/host capacity, admits bounded helper jobs and cancels optional work first. It may not silently shorten context, change a model, move private data to a remote provider or disable verification to fit resources. Keep runtime and policy changes explicit.
