# Model, harness and effort research

Checked 2026-09-25. This is an evidence-based starting policy, not a claim of a universal optimum. The [machine-readable registry](../config/evidence-registry.json) records source type, scope, observations and exclusions. Its source IDs are used by the decision catalog. Public benchmark results are priors; they do not qualify a local subscription route.

## Harness conclusion

The [HarnessTax study](https://arena.ai/blog/coding-agents-harness-tax) supports testing leaner execution, but its small sampled task sets and native effort semantics do not establish zero loss across projects. Its cost calculations are API equivalents. The owner's quota correction changes the objective: optimize verified useful work within finite subscription pools, not merely dollar cost. [OpenAI's usage guidance](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan) explicitly includes context and reasoning among consumption factors.

Do not remove safety or recovery to reduce prompt size. [ARC Prize's direct Astra measurements](https://arcprize.org/blog/astra) show a counterexample to universally minimizing scaffolding: retaining useful state can improve both outcomes and resource use. The engineering target is necessary context and effective state handling, not the smallest possible system prompt.

Keep both [Codex](harnesses/CODEX.md) and [Pi](harnesses/PI.md) profiles on main with shared policy. Codex is the rollout default because it preserves the existing worker path. Pi is a serious evaluation candidate, not a rejected option. Pi delegating to native workers and Pi running a native minimal model loop are different treatments. Do not claim the latter's savings for the former.

## Model and effort decisions

| Work | Starting menu | Basis and limitation |
| --- | --- | --- |
| Narrow routine changes | Luna low or high | Owner restriction plus workload evaluation; high is the substantive-work default. |
| Medium-tough implementation | Astra high; Opus5.5 medium or high | Equal competence tier, not equal measured quality on every task. Opus medium is a defensible efficiency starting point; high remains for denser reasoning or review. |
| Tough, architecture, research | GPT-6 Pro web plus Fable5.1 high or Opus5.5 high | Pro is the owner's required anchor. Select the Claude participant explicitly and bind it to case approvals. |
| Future successor | Fable5.5 pending | No verified release/access evidence; no invented slug or automated activation. |

[Opus documentation](https://platform.claude.com/docs/en/models/opus-5-5/overview) supports medium as its default. Its [launch evaluation](https://www.anthropic.com/claude-opus-5-5) supplies a reason to test that operating point, not a quota multiplier. [Astra launch results](https://openai.com/index/gpt-6-astra/) span best efforts and research environments; they cannot be relabelled GPT-6 Pro web results. Main/Extended benchmarks and differing fallback policies must remain separate.

The [Luna launch](https://openai.com/index/introducing-gpt-6-sol-and-luna/) does not establish high as a global mathematical optimum. The owner's chart motivates a high-effort candidate while preserving low for genuinely mechanical work. Reject xhigh/max from the shipped menu; revisit only with explicit policy change and measured end-to-end improvement. A point on a log-cost graph is not enough to determine optimal expected cost after retries.

## Domain specialization without folklore

Astra is a sensible prior for stateful tool work, intricate investigation and retained-context reasoning. Opus is a sensible peer for multi-file implementation, compact code and iterative UI work. Neither observation establishes a backend/frontend partition. Architectural frontend work still goes to Pro; a trivial backend edit does not.

The [Sonar first-hand Java evaluation](https://www.sonarsource.com/blog/claude-opus-5-5-an-evaluation/) includes both efficiency improvements and worse concurrency-related findings, so the catalog must not describe Opus as categorically safer. [Willison's Astra](https://simonwillison.net/2026/Sep/4/astra-pelicans/) and [Fable visual experiments](https://simonwillison.net/2026/Sep/1/claude-fable-5-1/) are useful artifacts but too narrow to establish production UI superiority. Controlled editorial comparisons across every requested exact model were not found. This gap is recorded instead of filled with anonymous opinions or SEO rankings.

## Promotion rule

Run matched local tasks for frontend, backend, debugging, integration, test writing and research handoffs. Preserve identical acceptance tests, tool access, scope and replayable evidence. Measure model/effort/harness combinations, including rework and final verification, in balanced order. Use held-out projects and time windows. Keep finite quota pools distinct. Promote only after quality and safety non-inferiority plus useful quota/latency gains; sample-size and tolerance decisions must be recorded before comparing outcomes. See [the quota protocol](QUOTA-EVALUATION.md).
