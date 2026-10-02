# Durable decisions

The initial published baseline was 8b96744 (2026-09-24). This record preserves its intent while explicitly superseding changed choices. Owner requirements are normative in OWNER-REQUIREMENTS.md.

## D001: shared GitHub baseline, retained

Keep complete reusable context, source, skills and tests on main. Read current Git state before editing, preserve concurrent work and update the handoff/status at closeout. Public specification is separate from private runtime evidence and credentials.

## D002: expanded primary model roles, amended 2026-09-25

Owner amendment: medium-tough work has Astra high and Opus 5.5 medium/high as peers. Deep work keeps GPT-6 Pro web and selects Fable 5.1 high or Opus 5.5 high for reciprocal review. Luna remains low/high only. Pending Fable 5.5 requires explicit release/access/regression activation.

## D003: real reciprocal review, retained and strengthened

Use actual participants, the same Pro case chat, immutable turns and exact-digest approval. Freeze Claude identity per epoch; switching it invalidates approvals while preserving history and open objections. Original local coordinator reconciles local facts and implements. Consensus does not prove correctness or grant authority.

## D004: CLM migration, supersedes previous backend

Owner amendment: use the pinned local contrastive state/action model. Reset previous calibration and cache assumptions. Store curated routing knowledge as JSON, render concise prose plus action descriptions, and keep hard eligibility outside the learned decision. Begin all operators in shadow mode.

## D005: dual harness packages, amended

Preserve custom Codex as the initial integration target and supply Pi on the same shared core. Native Pi and delegated Pi are separate measurement configurations. Claude subscription work uses the unmodified native worker; native Pi OpenAI access needs its own qualification. No divergent architecture branches are necessary.

## D006: manual Pro transport, retained

Current official Computer Use still excludes automating ChatGPT itself. Preserve manual ZIP/prompt continuation and exact chat binding. Automation needs a newly permitted, supported and tested path, not a workaround.

## D007: subscription efficiency, added

Owner clarification accepted: harness overhead can affect included usage. Optimize verified completed work against observed provider-specific quota and time. API-equivalent savings are not a quota conversion. No paid spillover or API fallback. Unknown attribution is not free usage.

## D008: bounded generation effort, added

Adopt the native apply/capture/ack ordering and short leases. Restrict model effort menus, honor manual overrides, invalidate stale state and keep model switches at worker boundaries. A setter's presence or synthetic fixture does not prove real cancellation/cache behavior.

## D009: evidence-ranked priors, added

Primary experiments, vendor claims, independent evaluations and firsthand editorial observations are separately labelled in the registry. Task-domain preferences are provisional except explicit owner-required floors. No universal backend/frontend winner or measured quota-optimal effort is claimed. Local held-out evaluation governs promotion.

## D010: preserve concurrent CLM work, added

The integration preserves concurrent commits through 294ebcb0, including f3538855 and 10592526, retaining the earlier revision ledger, its explicitly mapped requirement IDs and all 13 generic-choice tests. Keep its public imports stable using an unchanged compatibility module; new routing uses the stricter supervised client. Neither interface grants permission or proves deployment identity. The subsequent v1 routing/compiler source and its 25 tests remain available through an explicit compatibility boundary; active profiles use the v2 catalog. The six subsequent research/profile additions are retained with explicit active/supplemental mappings in INTEGRATION-RECONCILIATION.md.

For future entries record date, requirement impact, evidence, actual verification, alternatives and rollback. Do not silently replace history with a new unsupported certainty.

## D011: working runtime over further specification, added 2026-09-25

Owner Q&A: build a daemon that does real work now. `aa/` implements the flows with a
stdlib-only coordinator; `reference/` validators are kept but the runtime wins on
conflict. Compatibility layers (v1 routing, generic-choice CLM API) removed; Pi parked in
`parked/pi`; superseded docs moved to `docs/archive`. Rollback: previous commits on main.

## D012: deep flow Pro -> Opus x Astra -> Pro, supersedes D003

Pro drafts; Opus 5.5 high and Astra high co-edit through up to 5 rounds; Pro gives GO or
CLARIFY and implements after GO through the GitHub connector. Two CLARIFY reviews pause
the case. Rationale: at most ~2 manual Pro turns per case while keeping adversarial
challenge. Fable 5.1 dropped; Fable 5.5 later replaces Opus.

## D013: Pro transport via GitHub connector, supersedes D006

No ZIP. The owner pastes a one-line prompt (ntfy) into the case's Pro chat; Pro reads and
writes the private case branch. Automatic ChatGPT UI driving is still not used.

## D014: CLM zero-shot with abstention threshold, added

CLM is live from day one but zero-shot accuracy is limited (5/8 best wording on a probe
set, both tough examples missed). Votes below confidence 0.2 abstain; every decision is
logged with the final choice and outcome to enable fine-tuning. Owner resolves
disagreements, which also produces labels.

## D015: models switch, effort does not; no Codex fork, supersedes D008

Owner, 2026-09-25: with menus of Luna low/high and Astra high only, per-generation effort
switching would only ever affect Luna, whose effort the tier already fixes. Routing
switches models only. Medium-tough peers are Astra high and Opus 5.5 high.

## D016: SemIf replaces CLM as local decider, supersedes D014

Benchmark (eval/RESULTS.md): tier accuracy on a blind holdout — Codex triage 90%, SemIf
82%, keyword rules 57%, CLM zero-shot 38%. SemIf (Qwen3.5-4B typed option logits, in a
--network none container on a Unix socket) is the default decider; CLM services are
stopped but selectable (`decider.backend`). Rules are kept as a zero-cost backend and
benchmark baseline. Finding: as a second voter next to Codex triage, no decider lowered
total error cost; the owner decides whether to keep ask-on-disagreement.

## D017: spec-check loop with Opus 5.5, added 2026-09-26

Owner idea, tested first (eval/PROBES.md, blind 80-case spec set): SemIf per criterion
catches 70% of violations, Codex Luna low 100% with 20% false send-backs, Opus 5.5 medium
and high 40/40 with none (caveat: Opus also generated the set). Owner decision: Opus 5.5
judges every acceptance criterion and test tampering after the checks pass; unmet goes back
to the worker (which may rebut); max 3 loops, then the owner. Default effort medium.
Spec loops have their own budget and do not trigger lane escalation.

## D018: Claude worker guard = auto mode + hard denies, added 2026-09-26

Claude Code's OS sandbox needs nested user namespaces, which Ubuntu's AppArmor
bwrap-userns-restrict profile blocks (a claude-cli AppArmor profile did not help; the
restriction applies to bwrap's children). Owner chose not to loosen it system-wide.
Claude workers run with --permission-mode auto (classifier reviews every action; Bash is
not pre-approved) plus hard permission denies (git push/remote/config, sudo, ssh/scp, gh,
credential files) and --strict-mcp-config. `workers.claude_guard = "sandbox"` remains for
hosts that allow nesting. Verified live: normal work runs; an explicitly requested force
push was allowed by the classifier alone, hence the deterministic deny list.

## D019: failure triage wired in, added 2026-09-26

Failed checks are rerun once (FLAKY), then SemIf judges environment vs code (ENVIRONMENT
pauses and asks the owner instead of retrying/escalating), then the base commit is checked
(PRE_EXISTING does not trigger a blind retry; the spec judge is told the check still fails and
decides whether the task required fixing it; without the spec check it blocks as CODE).
Environment is asked before the base comparison because a broken environment breaks the base
commit too. Seen live on 2026-09-26: an auth/infra failure burned four worker attempts before
this existed.

## D020: oracle tests, mutation gate, cross-vendor best-of-2, added 2026-09-26

Owner chose research ideas 1+2, to trigger reliably by rule (aa/quality.py). Evidence:
agent-written tests inside the worker loop do not help; independent tests do; cross-vendor
candidate pools raise the chance a correct fix exists; judges prefer their own family, so the
pairwise pick uses a two-vendor panel. Live 2026-09-26: first run exposed a syntax-broken oracle
that escalated to Pro (fixed: validation, repair round, dispute safety net); second run
t0926-ac228 delivered end to end (both racers passed, both judges picked Astra).

## D021: Gemma 4 31B as local neutral judge and test writer, added 2026-09-26

From the owner's archive (only model that fits and fits the roles; Qwen3-Coder-Next and
Flash-Next do not fit). Served FP8 on loopback. Roles per research (heterogeneous teams,
self-preference of judges, local models only where output is verifiable): (1) tie-break when
the Opus/Astra pick panel splits, judged in both orders; (2) extra independent oracle test
set (main author in races). Measured 98% on the blind spec-conformance probe. It never
approves or vetoes on its own; its tests pass the same validation as any oracle.

## D022: deep-case reading list by BM25 over contents, not SemIf, added 2026-09-26

The BRIEF's reading list was triage paths plus files whose path contained a prompt word,
trimmed to 12 by SemIf. Benchmark on 100 real commits of pallets/click (commit message with
file names masked -> files the commit edited; `tools/bench_context.py`): recall@10 BM25 over
contents 0.63, SemIf on paths 0.50, SemIf on paths + first 40 lines 0.40, path keywords 0.28,
random 0.23; SemIf re-ranking a BM25 top 15 did not help (0.64). Dev and test halves agree.
Now: triage relevant paths first, then BM25 (`aa/retrieval.py`), no model. Commit messages
are cleaner than real requests, which flatters every method alike.

## D023: the owner's request is authoritative; triage criteria stay out of worker prompts, added 2026-09-28

Lab evidence (private research branch, results/noharness-r1, diag-r1..diag4): plain `codex exec`
with GPT-6 Astra high solved the ultra-hard lab projects 8/8, the aa simple pipeline 4/6. The
difference was one contract detail on u04_revenue (`restated: bool` on every monthly_revenue row).
The triage paraphrased it as "marks that month with restated: true" and invented an extra
requirement; workers followed the paraphrase and even rewrote docs/contracts.md to match. On aa's
own stage-1 code: original worker prompt 1/8, triage criteria as "hints" 6/8, no triage criteria
8/8, raw request 8/8.
Now: the worker prompt carries the request as authoritative, the repository's docs and contracts
as the definition of done, and no triage criteria; the reading list is "possibly useful starting
points". Oracle authors get no triage criteria. The spec judge keeps the criteria as a checklist
but judges the task as written as the last criterion and treats criteria as a paraphrase. Triage
must restate only what the request or repository requires and never add requirements. New guard:
edits to existing specification documents (contract/spec/interface/requirement/api files, spec(s)/
and contract(s)/ directories) are recorded, shown to the spec judge with the original text, and
named in the delivery result.

## D024: the simple pipeline is the default; the full pipeline's stages are opt-in, added 2026-09-28

Owner decision after the overnight lab rounds (private research branch, results/u04-confirm-r1,
u04-confirm-full-r1, u04-luna-r1, noharness-luna-r1). On the four ultra-hard lab projects, with D023:
simple pipeline 8/8 in 8.9 min, equal to plain `codex exec` Astra high (8/8, 8.5 min); full pipeline
3/4 in 19.7 min. Its spec judge found a real ambiguity the hidden tests do not check and handed back a
delivery that passed every hidden test. Before D023 the full pipeline was 7/8 vs 6/8 at twice the time,
and the earlier task suite (ho01-r1b) showed no gain either.
Now off by default: oracle tests with the mutation gate, the best-of-2 race, the spec check and failure
triage. The code and tests stay and each can be enabled in aa.toml, but none is recommended until a new
measurement shows a gain. Findings kept for later: the spec judge is good at spotting real ambiguities,
so a non-blocking "flag it to the owner" variant may be worth measuring. The race picked Opus only on the
sync project. The contract-edit guard of D023 stays on (it only records and reports).
Also on by default: Codex workers run with memory use and generation switched off per call
(`workers.codex_no_memories`), as in every lab arm, so the owner's personal Codex memories never reach
harness workers. The subscription login is not touched.
Luna finding for routing: Luna high solved 2-3/8 of the ultra-hard projects with or without aa and always
passed the visible checks, so escalation on failed checks never fired. Routing hard work to Astra has to
rely on the triage tier (or a stronger trigger), not on check failures.

## D025: local-first lane (experimental, off by default), added 2026-09-28

Round A (private research branch, results/local-a-r1, local-a-diag): Codex can drive the local Gemma 4 31B
(vLLM with the gemma4 tool and reasoning parsers, 128k context) as a worker at zero subscription quota. Plain
local Gemma solved 13/24 of the ho01 DEV tasks (aa on Luna: 80%). 4 of the 24 runs ended after one sentence
without any tool call.
Built for round B, all behind `local_first.enabled` (off): lane `gemma_codex` (Codex with a loopback
provider, no subscription check), routing of the configured tiers to it first, one free nudge after a turn
that changed nothing, and after the checks pass a mandatory independent review of the diff against the
request (the spec judge, on `local_first.review_lane`, default Luna high), even when `spec_check` is off.
Review findings or exhausted local passes escalate to the lane the tier would have used, which continues in
the same worktree with the findings. No review loops with the local model.
The owner rejected "escalate only on failed checks": the visible tests miss new requirements (Luna rounds),
so quality must not depend on someone adding tests.
Correction after round-b-r1 (stopped after 4 trials): with `--output-schema`, vLLM enforced the JSON format on
every turn, so the local model could not call tools and answered at once ("partial", or invented results). The
local lane now gets the schema in the prompt and aa parses the last JSON object of the final message; the
`routine` tier is included in `local_first.tiers` (the easiest work is the best fit for the local model).

## D026: configurable worker lanes for routine and bounded tasks, added 2026-09-28

`tier_lanes.routine` / `tier_lanes.bounded` (defaults unchanged: Luna low / Luna high) select the worker
for those tiers. Purpose: round C tests the owner's idea of Claude Opus (Claude Code subscription) in
Luna's roles; round B (private results/round-b-r2) showed that on small tasks the per-task fixed cost
(triage, review) decides the quota, so the reviewer and small-task worker are the levers. An unknown lane
name is an error. Failed passes escalate as before (to the medium-tough peers, then a deep case).

## D027: GPT-6 Luna always at high effort, added 2026-09-28

Owner decision after the published effort curves (DeepSWE by cost per task; Artificial Analysis index for GPT-5.6
Luna): Luna at low effort is far weaker for a few cents less per task. `tier_lanes.routine` is now `luna_high`
(bounded already was). Opus as a builder always runs at high (`opus_high`, as for hard tasks); the Opus reviewer
stays at medium, where medium and high both scored 40/40 on the review probe (D017). Lab rounds before
2026-09-28 23:00 used Luna low for routine tasks; comparisons within a round are unaffected.


## D028: Claude Opus 5.5 builds routine and bounded tasks; no review by default, added 2026-09-29

Owner decisions after rounds C and D (private results/round-c-r2, round-d-r2):
- `tier_lanes.routine` and `tier_lanes.bounded` default to `opus_high`. Round C, same 12 practice tasks twice:
  Opus 23/24 vs Luna 21/24 at the same speed, with a third of Luna's Codex tokens. The cost is Claude
  subscription quota (about 4 USD API-equivalent per 24 tasks at medium). Failed passes go to the other
  medium-tough peer (Astra high), then to a deep case. Opus builds at high (D027). Round C measured medium.
- The review of each delivery (`spec_check`) stays off by default (D024). In round D, both review arms scored
  20/24 and the same tasks without a review 21/24; the review caught none of the wrong deliveries. It remains
  opt-in, e.g. for risky areas.

## D029: confidence check with a rework lane (opt-in, round F), added 2026-09-29

`confidence_check.enabled` (default off). After the checks pass (and after the spec review, if on), an independent
read-only model (`lane`, default Opus 5.5 medium) reads the worktree and rates the probability that the change meets
the request, including what a careful maintainer would expect without being told (`prompts/confidence_check.md`,
the checklist prompt tested in private results/confidence-r2: AUROC 0.90 on 63 real deliveries, 16 of 21 wrong ones
flagged at 6 of 42 right ones, p < 0.75). If p >= `threshold` (0.75), the change is delivered. Otherwise the rework
lane (`fable_high`, Claude Fable 5.1 high) takes over the same worktree with the check's points (one rework,
`max_reworks`), and the checks and the confidence check run again. Still below the threshold after that, the task
opens a deep case (GPT-6 Pro / the owner). The owner proposed this chain; round F measures it live before it can
become a default. The delivery note states the last check's probability.

## D030: builders state their assumptions; the owner sees them, added 2026-10-01

Every builder answer has an `assumptions` list: choices made where the request, the code and the tests were silent. aa
keeps them per lane and lists those of the delivered lane in the delivery commit and the ntfy Done message, under
"Assumptions (check these)".
- **Why:** in private results/ask-r1, aa asked the owner only when a value was missing outright and guessed otherwise
  (8 of 10 right). The wrong guess was invisible. With this change, both runs of that task named the decisive guess.
- **Regression check:** practice suite, 20 runs, 15 correct; every task at its usual rate.
- Owner decision, 2026-10-01.

## D031: builder choice for medium-tough work stays; no GPT-6.1 Sol lane, added 2026-10-01

On 20 real Apache Superset fixes (private results/round-h-r1), GPT-6 Astra, GPT-6.1 Sol and Claude Opus 5.5 working
alone were not distinguishable in correctness: 7, 7 and 5 of 20; paired differences within about ±0.2, p between 0.6
and 1.0. Astra was the fastest. Sol matched Astra's outcomes with 65% more tokens and 1.7× the time.
- The decider keeps choosing between Astra and Opus for medium-tough tasks.
- No Sol lane is added.
- Owner decision, 2026-10-01.

## D032: research phase offered for new projects, added 2026-10-02

Owner decision (2026-10-02): for a new project, aa first offers a research phase. "New" means a repository with at most
`new_repo_max_commits` (3) commits and at most `new_repo_max_files` (40) files, i.e. young and small, not a small
long-lived repository. The offer is one ntfy question with the
buttons "Research first" (`research <id>`) and "Skip" (`noresearch <id>`), and it comes at most once per repository.

On "Research first", a read-only Claude call (`research_phase.lane`, Opus 5.5 high) may use WebSearch and WebFetch and
writes a brief from `prompts/research.md`: prior art, papers and methods, designs and pitfalls, open questions, and the
sources it actually opened. The brief:
- goes to the owner by ntfy;
- is saved under `state/research/<id>.md`;
- reaches the builder as context, while the request stays authoritative.

Live check: a toy rate-limiter project got a brief with 21 sources in 170 s, for about $1.20 API-equivalent. Switch:
`research_phase.offer`.

## D033: research only on the owner's request, added 2026-10-02 (amends D032)

Owner decision (2026-10-02): research can be needed in older and larger projects too, so the owner decides when to
research rather than aa guessing from the repository's age and size.

- The automatic offer for new projects is off by default (`research_phase.offer = false`). The D032 offer still
  works if it is switched on.
- The owner asks for research in either of two ways:
  - when creating the task: `aa task --research "..."`;
  - on a task that has not reached a builder yet (status NEW or TRIAGED, or a pending offer): the reply
    `research <id>`.
- Later, the reply is refused with a "Reply not applied" ping.
- The research call itself is unchanged from D032: Opus with web search writes a sourced brief for the owner and the
  builder, and the request stays authoritative.
