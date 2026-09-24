# Start here: AgenticArch

This repository is the durable, public project context for co-development across coding sessions and machines. A new session must read the repository, not rely on an earlier chat or an old downloadable archive.

## Resume a session

Read [agent instructions](AGENTS.md), [the current handoff](docs/SESSION-HANDOFF.md), [owner requirements](docs/OWNER-REQUIREMENTS.md), and [implementation status](IMPLEMENTATION-STATUS.md). Then read the specifications and exact files relevant to the task. For first implementation on the workstation, use [the implementation prompt](prompts/IMPLEMENT-AGENTICARCH.md).

`main` is the shared integration baseline. Before editing, inspect the actual remote head, local branch and worktree. Preserve existing edits. When another session has advanced the repository, reconcile its changes before publishing; never force-push or silently replace them. Sessions doing overlapping work should use separate branches/worktrees and integrate reviewed increments.

## What you are starting from

The repository includes the architecture, explicit requirements, researched SemIf opportunities, policy, schemas, two revised skills, case templates, implementation prompts, reference code and offline tests. The complete local runtime is not implemented or qualified. See [the validation report](docs/VALIDATION-REPORT.md) for tested scope and [the handoff](docs/SESSION-HANDOFF.md) for the next concrete work.

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_kit.py
python3 tools/demo_decision_plane.py
```

These are offline kit checks, not proof of working local model integrations.

## Carry context forward

After each meaningful work session, update [the handoff](docs/SESSION-HANDOFF.md) with changes, actual verification, unresolved issues and the next action. Update [implementation status](IMPLEMENTATION-STATUS.md) when capabilities change. Record durable design decisions in [the decision log](docs/DECISIONS.md), linking supporting requirements and evidence. Keep normative requirements and machine-readable policy consistent.

Commit source and documentation together when authorized. Report the actual branch and remote commit after readback. A local commit does not establish successful publication.

The public repository is not a store for every byte of runtime context. Credentials, private chat bindings, real case bundles, local capability reports and customer data remain private. The operational review workspace is `GPT-Pro-Escalation`; its creation/access and real data exports require scoped authorization. Include only sanitized summaries here.
