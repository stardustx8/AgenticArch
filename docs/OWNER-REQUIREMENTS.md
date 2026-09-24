# Owner requirements and decision record

Version 1.2 · 2026-09-24 · normative requirements, not a claim of live implementation.

## Purpose and priorities

Deliver a self-contained architecture and implementation kit that the owner's local AI coding agent can implement. Optimize reliable, high-quality completed work, tailored to the actual environment, with sensible compute use. Avoid treating the existing setup as immovable: the owner explicitly permits proposing changes where they materially improve the result. Openness to a change is not blanket permission to install software, export data, weaken controls, or incur new costs.

The reusable public specification lives in `stardustx8/AgenticArch`. The operational deep-review repository is named `GPT-Pro-Escalation`. Neither public release nor model consensus grants extra operational authority.

## Owner-stated requirements

| ID | Requirement | Implementation/acceptance link |
| --- | --- | --- |
| R01 | Produce a complete, standalone implementation package: architecture, guidance, machine-readable policy, tests, and one entry prompt. | `README.md`; `prompts/IMPLEMENT-AGENTICARCH.md`; `tools/check_kit.py` |
| R02 | Initialize and publish the package to AgenticArch, keeping the actual delivery state truthful. | `docs/PUBLISHING.md`; remote commit and file readback |
| R03 | The public package must be self-contained and understandable without private source material. | Publication hygiene and link checks |
| R04 | Use GPT-6 Luna at **low or high only**. | Policy validation and lane tests |
| R05 | Use GPT-6 Astra **high** for medium-tough implementation/debugging. | Complexity-floor tests |
| R06 | Tough work, architecture-level work and research go directly to **GPT-6 Pro in ChatGPT web**. No mandatory failures in lower lanes first. | Routing tests; Pro case receipts |
| R07 | Invoke `prepare-sol-pro-architecture-review` for this deep-work handoff; keep that exact legacy identifier. | Revised skill; policy field |
| R08 | Package the relevant evidence into a ZIP and provide an accompanying prompt that asks Pro to work in `GPT-Pro-Escalation`. | Packaging manifest; handoff template; case-path checks |
| R09 | Desired operation: Codex Computer Use submits ZIP and prompt to the Pro web conversation. This is conditional on platform support and authorization. | `docs/COMPUTER-USE-GATE.md`; unsupported capability must not be advertised as working |
| R10 | Automatically activate `fable-adversarial-review` after Pro's complete initial contribution is durable. | Verified completion receipt, not spinner disappearance |
| R11 | Pro and Fable adversarially challenge and improve each other's work through the review repository. | Real participant receipts, immutable turns and `DIALOGUE.md` |
| R12 | Each further Pro round continues the **same established chat for that case**. | Exact private conversation binding; no `last chat` heuristic |
| R13 | Continue until both agree about the co-produced result. Resource/permission/input pauses are resumable, never fabricated agreement. | Matching approvals; open-objection and pause tests |
| R14 | The original local Codex session fetches the agreed version and implements it as closely as possible. | Pinned commit; original task/session binding |
| R15 | Navigate local facts the reviewers could not know. Preserve design intent; record local adaptations; reopen material design changes for review. | `LOCAL-DELTA.md`; local verification gates |
| R16 | Use locally running **SemIf** for bounded semantic decision support. No hosted routing dependency. | Local-only adapter; timeout/fallback tests |
| R17 | Revise the two actual skills directly, not by delivering skill-upgrade prompts. | `skills/prepare-sol-pro-architecture-review/`; `skills/fable-adversarial-review/` |
| R18 | Preserve useful evidence packaging, independent challenge, citations, scoped permissions and manual recovery from the skills. | Skill definitions and self-contained references |
| R19 | The primary host is the owner's AI workstation, with custom Codex capable of using local and remote models. Do not assume an unmodified client. | Read-only local capability inventory before implementation |
| R20 | Local models and tools may support tailored solutions; setup amendments and novel architectures are welcome when justified. | `docs/WORKSTATION-DESIGN.md`; optional enhancement evaluation |
| R21 | Document requirements explicitly, distinguish owner requirements from engineering choices, and map them to acceptance checks. | This document; `docs/ACCEPTANCE-TESTS.md` |
| R22 | Research the creative possibilities of local semantic decision models beyond routing, and incorporate highly useful cases with evidence and qualification gates. | `docs/SEMANTIC-DECISION-OPPORTUNITIES.md`; `docs/DECISION-PLANE.md`; `docs/DECISION-EVALUATION.md` |
| R23 | Keep the complete reusable solution and development context on GitHub so future sessions and machines can resume and co-develop from the repository. Maintain a current handoff, status and durable decisions; preserve concurrent work and private runtime boundaries. | `START-HERE.md`; `docs/SESSION-HANDOFF.md`; `docs/DECISIONS.md`; verified remote publication |

## Reference environment, not a dependency lock

Owner-reported reference hardware: one NVIDIA RTX PRO 6000 Blackwell Workstation Edition with 96 GB VRAM and 128 GB ECC system memory. Linux is the intended AI runtime. Custom Codex supports local and remote model use. These are planning inputs; driver/runtime versions, actual free memory, local model endpoints, tool schemas, browser capabilities and current availability must be discovered on that workstation. No motherboard, private address, serial number or authentication material is needed in the public package.

The existing skill names are exactly `prepare-sol-pro-architecture-review` and `fable-adversarial-review`. The first name is retained for invocation compatibility; it **does not select the model implied by its historical name**. The kit supplies complete `SKILL.md` definitions and their referenced templates. Auxiliary installed scripts are local integration inputs; installation must inspect and preserve unrelated helpers rather than claim they were reviewed.

## Selected engineering decisions, changeable with evidence

The owner did not prescribe these implementation details:

- One local coordinator, SQLite state/outbox and ordinary Git. No distributed agent platform for the first release.
- Required routing floors, typed adapter contracts, fail-closed side effects, immutable receipts and content-digest approvals.
- Private review repository for real cases; per-case branches; one serialized writer per case; local-only browser/session state.
- SemIf starts in shadow mode, then advisory routing after workload evaluation. It cannot waive deterministic checks or authorize completion.
- Configurable retry and debate budgets pause uncontrolled work without claiming convergence. Values in `config/policy.json` are starter operational defaults, not empirically optimal thresholds or new product requirements.
- Optional local context retrieval and sandboxed counterexample generation are evaluated before enabling them. More agents are not automatically better.

## Known capability gap: requested automatic Pro web submission

The official Computer Use documentation inspected on 2026-09-24 describes macOS/Windows and explicitly excludes automating ChatGPT itself. Therefore the stock integration is **not qualified** for R09. The supported starting workflow is explicit manual upload/continuation, retaining the same Pro model, repository and case/chat protocol. The adapter has a conditional automation contract for a future explicitly permitted and verified capability. A custom client is not proof of permission or support. Do not replace this requirement silently with an API model, nor route around the restriction with another automation tool. See [the capability gate](COMPUTER-USE-GATE.md) for the official source and activation requirements.

## Acceptance and changes

Local discoveries may refine paths, versions and adapter choices. They may not silently weaken R04–R16. A proposal to change model policy, target transport, data semantics or security is recorded with rationale and owner decision. Requirements and acceptance criteria are hashed into every case so an old approval cannot approve a new problem.
