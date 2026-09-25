# AgenticArch

Local CLM decision support, subscription-backed coding, and evidence-driven deep review.

## Start here

Read [START-HERE.md](START-HERE.md), [the current handoff](docs/SESSION-HANDOFF.md) and [owner requirements](docs/OWNER-REQUIREMENTS.md). Both harness packages live on `main` and share one policy, not competing architecture branches:

| Package | Execution path | Status |
| --- | --- | --- |
| [Custom Codex](harnesses/codex/README.md) | Native Codex subscription workers; unmodified Claude Code workers | Primary integration target; workstation qualification pending |
| [Pi](harnesses/pi/README.md) | Pi coordinator with subscription workers; optional qualified native OpenAI path | Alternative integration target; no direct Claude subscription-token bridge |

Native Pi and Pi delegating to another harness are different systems. A delegating Pi profile retains worker overhead and cannot claim native-Pi benchmark savings. Subscription efficiency matters, but API dollar savings do not convert into a fixed percentage of quota savings. See [the harness decision](docs/HARNESS-DECISION.md).

## Model policy

| Work | Permitted selection |
| --- | --- |
| Narrow mechanical next step | Luna low |
| Substantive bounded implementation/debugging | Luna high |
| Medium-tough implementation in an approved design | Astra high **or Opus 5.5 medium/high**, equal-tier peers |
| Tough work, architecture, research, consequential design | GPT-6 Pro in ChatGPT web, plus **Fable 5.1 high or Opus 5.5 high** for reciprocal challenge |

Fable 5.5 is a disabled pending successor, not an assumed release. An API slug in the catalog identifies a model; it does not authorize API billing. Pro's logical identifier is not an API endpoint.

```text
Owner task -> deterministic policy and subscription eligibility
           -> local CLM: compact state + permitted action descriptions
           -> selected Codex or Pi profile -> actual worker
           -> generation-boundary effort lease + effective-setting readback
           -> actual tools/tests and evidence
           -> deep work: same Pro chat <-> selected Claude in GPT-Pro-Escalation
           -> exact-version agreement -> original coordinator implements locally
```

CLM replaces the decision backend. It does not write policy, grant permissions, certify test success or approve the final implementation. The [JSON routing catalog](config/model-routing.json) includes models, efforts, task priors and decision templates. The [evidence registry](config/research-evidence.json) distinguishes primary benchmarks, official documentation, firsthand editorials and owner choices. Model-facing inputs are concise prose and typed choices, not the entire registry.

## What is actually delivered

An implementation kit with runnable reference code, a loopback-only CLM HTTP adapter, routing qualification, effort acknowledgments, quota attribution, revised skills, schemas, both harness packages and offline tests. It is **not an installed autonomous runtime**. Real CLM inference, provider quota accounting, patched Codex and native Pi integration must be exercised on the workstation. [Status](IMPLEMENTATION-STATUS.md) and [validation](docs/VALIDATION-REPORT.md) record the boundary.

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_kit.py
python3 tools/demo_decision_plane.py
python3 tools/preview_routing.py --harness codex
```

The preview uses synthetic bindings and does not call a provider. Install the two directly revised [skills](skills/README.md) only after a dry run and a backup of the actual local trees. The first implementation entry point is [IMPLEMENT-AGENTICARCH.md](prompts/IMPLEMENT-AGENTICARCH.md).

## Deep-review continuity

Keep the exact identifiers `prepare-sol-pro-architecture-review` and `fable-adversarial-review`. Every Pro continuation stays in the case's established web chat. The Claude participant's exact model is frozen per review epoch. A participant change invalidates approvals; old turns remain in history and unresolved objections carry forward.

Standard Computer Use currently excludes automating ChatGPT itself. Manual Pro ZIP/prompt transfer remains the default, with an explicit [capability gate](docs/COMPUTER-USE-GATE.md), not an automation bypass.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [CLM adapter](docs/CLM-ADAPTER.md) · [Dynamic effort](docs/DYNAMIC-REASONING.md) · [Model evidence](docs/MODEL-EVIDENCE.md) · [Quota evaluation](docs/SUBSCRIPTION-EVALUATION.md) · [Implementation plan](docs/IMPLEMENTATION-PLAN.md) · [Review protocol](docs/ESCALATION-PROTOCOL.md) · [Security](docs/SECURITY-AND-OPERATIONS.md)

Publish reusable source and sanitized development context only. Credentials, private chat bindings, customer material, local capability inventories and live cases do not belong in this public repository. `GPT-Pro-Escalation` is the separate review workspace, not provisioned by this kit.
