# Primary sources for the semantic decision design

Verified on **2026-09-24**. These are technical references, not dependencies or endorsements. Public project URLs may redirect after renames; pin the actual installed revision during local integration. No source's advertised speed or quality is a target-workstation measurement.

| ID | Source | Supported point and limitation |
| --- | --- | --- |
| S01 | [SemIf method](https://github.com/TheoLeeCJ/SemIf/blob/master/docs/METHOD.md) | Frozen open-model direct option-logit scoring; runtime criteria; 2–16 described options in the published baseline. Not a reproduction of a proprietary architecture. |
| S02 | [SemIf results](https://github.com/TheoLeeCJ/SemIf/blob/master/docs/RESULTS.md) | Repeated-state execution and quality experiments, including numerical/ordering drift and limits. Results are task/backend-specific. |
| S03 | [SemIf calibration](https://github.com/TheoLeeCJ/SemIf/blob/master/docs/CALIBRATION.md) | Workload-specific temperature scaling with group-disjoint evaluation. Calibration does not improve argmax accuracy. |
| S04 | [RouteLLM](https://arxiv.org/abs/2406.18665) | Learned strong/weak model routing predates the present interface. Its benchmarks do not establish current lane-specific savings. |
| S05 | [Typed decision primitives](https://docs.typesafe.ai/introduction) | Atomic questions composed by ordinary software. Hosted interface details are not promised by SemIf. |
| S06 | [Speculative fan-out](https://docs.typesafe.ai/patterns/fan-out) | Ask independent snapshot questions together, then use the relevant answers. No guarantee that local extra questions are free. |
| S07 | [Original experiments: goal hierarchies and tournament choice](https://www.seangoedecke.com/two-techniques-for-working-with-system-one-models/) | September 18, 2026 prototype demonstrations. Useful patterns; not a coding-agent evaluation or workstation benchmark. |
| S08 | [System-One-controlled agentic memory, v1](https://arxiv.org/html/2609.23986v1) | September 21, 2026 preprint separating memory control/storage/reasoning. Conversational-memory evaluation, not SemIf coding deployment. See caveat below. |
| S09 | [SayCan](https://research.google/pubs/do-as-i-can-not-as-i-say-grounding-language-in-robotic-affordances/) | Earlier work grounding semantic plans in actual available skills. Transfer to coding playbooks is our design inference. |
| S10 | [CodeRAG-Bench](https://arxiv.org/abs/2406.14497) | Useful external context can improve code generation; retrieval and context integration also fail. Supports evaluation, not automatic replacement of an existing retriever. |
| S11 | [On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599) | Calibration as a separate empirical problem; temperature scaling is not correctness proof. |
| S12 | [Proposal: distilling repeated decision calls](https://www.seangoedecke.com/system-one-models-can-train-their-own-replacements/) | September 20, 2026 design proposal, not a reported successful training experiment. AgenticArch strengthens it with independent labels and release gates. |
| S13 | [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) | CaMeL's explicit control/data separation and capabilities. AgenticArch is not a CaMeL implementation and inherits no formal guarantee. |
| S14 | [Confidence semantics](https://docs.typesafe.ai/confidence) | Confidence may be a statistic of the option distribution, not a separate correctness observation. Do not map hosted confidence directly onto SemIf probabilities. |
| S15 | [Composite scoring](https://docs.typesafe.ai/patterns/composite-scoring) | Keep separate dimensions and explicit application weights. A weighted rank score is not a calibrated probability. |

## Preprint caveat

S08 provides useful architecture-level ideas, but its current results narrative disagrees with some entries in Table 1 (for example, the temporal result), and the prose says “five of six categories” while the table has five task categories plus the overall column. We do not rely on its numerical advantage in this design. These presentation issues are not proof the method fails; they are reasons to reproduce it before adopting a performance claim.

## Scope of this research

The strongest direct evidence here is an inspectable local scoring implementation and its documented limitations. Hosted demonstrations and a new preprint are weaker evidence for this owner's workload. The decision operators, event model, diagnostics, memory policies and adoption order are **AgenticArch proposals**, to be tested locally. No additional model/provider was activated or installed during preparation.
