# Decision benchmark (CLM vs SemIf vs Codex)

Labelled, realistic coding and knowledge-work requests for the two semantic decisions
`aa` makes: the **tier** (routine / bounded / medium_tough / tough) and, for
medium-tough work, the **peer model** (GPT-6 Astra vs Claude Opus 5.5).

Files: `decisions/tier.jsonl` (one task per line). Fields: `id`, `domain`
(coding|knowledge), `area`, `text` (the request as an owner would type it), `tier`,
`peer` (astra|opus, only for medium_tough and peer-only rows), `split` (dev|test).
Phrasings/prompts are chosen on `dev`; results are reported on `test`.

Run: `python3 tools/eval_decisions.py --backends clm,semif[,codex]` (see --help).
Reports go to `eval/results/`.

## Labelling guide

Pick the **lowest tier that can do the task well** (the owner's routing rule).

| Tier | Coding | Knowledge work |
| --- | --- | --- |
| routine | rename, typo, config value, bump a version, one-line fix, add a log line | reformat, fix spelling, convert a table, rename headings |
| bounded | ordinary bug fix or small feature in a few files with clear acceptance; add tests; a CLI flag; one endpoint | summarize one document, draft an email or README section, write a changelog |
| medium_tough | several interacting modules, concurrency, performance, tricky debugging, security-sensitive implementation inside an existing design, non-trivial refactor | synthesis across several sources, comparative evaluation with evidence, a technical explainer that must be correct |
| tough | architecture/system design, research with an open question, data migration design, security design, irreversible changes, unclear approach | strategy, open-ended research with conclusions, design proposals, decisions with long-term consequences |

Any architecture, research, security design, migration design or irreversible design
makes the task **tough** (mandatory Pro).

Peer (medium_tough only): **astra** for backend, systems, algorithms, data, infra,
concurrency and debugging; **opus** for frontend, UI/UX, visual and interaction work,
product and writing-heavy tasks. These are the owner's stated priors, not measured truth.

Labels were written by Claude (Opus 5.5) on 2026-09-25 following this guide; the owner
may correct any row — the benchmark is only as good as its labels.
