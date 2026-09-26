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
