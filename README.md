# AgenticArch

Evidence-driven, local-first orchestration for AI coding agents.

AgenticArch separates code generation, bounded semantic decisions, deterministic verification, and deep adversarial review. A small local controller enforces the workflow; prompts do not impersonate model switching, verification, or approval.

## Model policy

| Work | Required lane |
| --- | --- |
| Routine, narrow, well-specified edits | GPT-6 Luna **low** |
| Bounded implementation and debugging that needs more reasoning | GPT-6 Luna **high** |
| Medium-tough implementation and debugging | GPT-6 Astra **high** |
| Tough problems, architecture, research, consequential design decisions | **GPT-6 Pro in the ChatGPT web interface**, through `prepare-sol-pro-architecture-review` |

Only `low` and `high` are allowed for Luna. Architecture and research go directly to Pro: they do not have to fail through cheaper lanes first. SemIf runs locally and supplies typed decision support, never authority to bypass policy or evidence.

## Deep-work cycle

```text
Local Codex session
  -> prepare-sol-pro-architecture-review: snapshot + redacted ZIP + prompt
  -> Pro web transfer: manual by default; qualified UI automation only
  -> bind one GPT-6 Pro chat to one case
  -> GPT-Pro-Escalation: Pro authors the initial solution
  -> fable-adversarial-review: Fable challenges; Pro responds in the SAME chat
  -> shared DIALOGUE.md + versioned solution + evidence
  -> repeat until both approve the SAME solution digest
  -> local Codex fetches the pinned result, checks local differences,
     implements faithfully, and verifies the actual changed software
```

Agreement is a review gate, not proof. A safety or resource pause is resumable and is never reported as convergence.

## Start here

For a new session or machine, read [START-HERE.md](START-HERE.md) and [the current session handoff](docs/SESSION-HANDOFF.md). GitHub `main` is the durable project baseline; source, requirements, decisions and verification context are maintained together.

Give your local coding agent [the implementation prompt](prompts/IMPLEMENT-AGENTICARCH.md). It includes discovery, implementation order, direct integration of the two custom skills, tests, and rollout gates.

The two [revised skills](skills/README.md) are included, using their exact existing identifiers. Install them through the dry-run-first installer after locating the current custom Codex skill directories. No separate skill-upgrade prompts are included.

**Pro web automation has a real capability gap:** current standard Computer Use guidance excludes automating ChatGPT itself. This kit defaults to manual Pro upload/continuation and preserves a conditional, permission-gated automation interface. See [the transport gate](docs/COMPUTER-USE-GATE.md).

Read [the architecture](docs/ARCHITECTURE.md), then [the implementation plan](docs/IMPLEMENTATION-PLAN.md). The detailed review protocol is in [the escalation specification](docs/ESCALATION-PROTOCOL.md).

## What is implemented here

This is an implementation kit with normative documentation, configuration, schemas, prompts, case templates, a dependency-free **reference policy kernel**, and offline tests. It is **not** an already-connected autonomous coding service. Live Codex, SemIf, Fable, permitted browser transport, Git synchronization and persistent-state adapters must be implemented and verified locally. See [implementation status](IMPLEMENTATION-STATUS.md).

Run offline checks with Python 3.11 or newer:

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_kit.py
python3 tools/demo_decision_plane.py  # Synthetic scores; no model call
```

No model calls, browser actions, credentials, or package downloads are needed for these checks.

## Public specification, private execution

This repository contains generic engineering material only. Real case bundles, chats, credentials, telemetry, and customer material stay out of it. The separate `GPT-Pro-Escalation` repository is the review workspace; use private visibility for real cases. A private repository still involves external disclosure and needs an explicit export policy.

Use a single local controller and ordinary Git first. No distributed scheduler, hosted routing service, or always-on model debate is required.

## Navigation

- [Owner requirements](docs/OWNER-REQUIREMENTS.md)
- [Workstation-first design](docs/WORKSTATION-DESIGN.md)
- [Revised skills and installation](skills/README.md)
- [Publication and recovery](docs/PUBLISHING.md)
- [Routing and evidence gates](docs/ROUTING-AND-VERIFICATION.md)
- [SemIf integration contract](docs/SEMIF-ADAPTER.md)
- [Security, recovery, and operations](docs/SECURITY-AND-OPERATIONS.md)
- [Acceptance scenarios](docs/ACCEPTANCE-TESTS.md)
- [Integration references](docs/INTEGRATION-REFERENCES.md)
- [Contribution guidance](CONTRIBUTING.md)

## Beyond model routing

[Researched semantic-decision opportunities](docs/SEMANTIC-DECISION-OPPORTUNITIES.md) extend the design to adaptive context, requirement gaps, next diagnostics, local memory and Pro/Fable review triage. The [decision-plane specification](docs/DECISION-PLANE.md), operator catalog and offline reference helpers make those ideas implementable without claiming live SemIf performance. All new operators start in shadow mode.

See the [worked example](docs/WORKED-EXAMPLE.md) and [offline validation report](docs/VALIDATION-REPORT.md) for the distinction between contract checks and live integration evidence.
