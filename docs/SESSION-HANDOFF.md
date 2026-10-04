# Session handoff

Updated 2026-09-28 morning (Claude Code session on the workstation, branch `m1-working-runtime`).

## State

The `aa` runtime is installed and running on the workstation (see
[IMPLEMENTATION-STATUS](../IMPLEMENTATION-STATUS.md) for what was verified live). Owner
decisions are in [OWNER-REQUIREMENTS](OWNER-REQUIREMENTS.md) (O01-O19) and DECISIONS
D011-D022. PR #2 (`m1-working-runtime`) is open for the owner.

Added 2026-09-26: Gemma 4 31B (vLLM FP8, `aa-gemma`) as neutral judge and extra oracle
author (D021); oracle tests, mutation gate, best-of-2 race (D020); idea flags; the harness lab
(`tools/lab.py`, tasks in `eval/lab/tasks/`); fixes found by the lab (oracle disputes, owner
question cap, model-call cap, hang-safe grading); daemon memory cap (48G, OOMPolicy=continue);
deep-case reading list by BM25 (D022). GPU ECC is enabled (no capacity loss).

## Harness optimisation with GPT Pro (HO-01)

- Private branch `research/harness-opt-01` of stardustx8/Dashboard (local clone
  `~/dev/GPT-Pro-Escalation`): BRIEF.md, inputs, owner answers and work profile, Pro's
  REPORT/SCORING/EXPERIMENTS, reviews, results, turn files (`turns/PRO-TURN-NN.md`).
- Pro's code: AgenticArch PR #3 (`pro/harness-opt-01`), draft, all new policies off by default.
  Lab rounds run from a pinned detached worktree (currently
  `~/dev/GPT-Pro-Escalation/.ho02-local/code`, never the main checkout); local round output in
  `~/dev/GPT-Pro-Escalation/.ho02-local/`, round-1 records in `~/ho01-runs-20260926/`.
- After starting any long round, check the first ~15-25% of results for validity (ceiling,
  artefacts, leakage) before letting it run on (owner, 2026-09-27).
- Round 1 (`ho01-r1b`, 120 runs): minimal 80% in 1.1 min, full 77% in 2.7 min; full
  regresses `b1_statement_amounts` (drops existing input rejection) 4/5 times. With the owner's
  trade-off (O18: 2 pp less correct is fine for 2x faster) the minimal pipeline is currently the
  better deal on these tasks; the task suite does not yet represent the owner's work (O19).
- Project round 2 (`ho02-project-r2`) was stopped after 18/60 trajectories: most projects at
  ceiling, and a Pro-escalation artefact (no GitHub origin in the lab). Pro turn 03 redesigns. When it ends: review the diff with a fresh subagent, run EXPERIMENTS.md rounds from
  the worktree under `systemd-run --user -p MemoryMax=48G -p OOMPolicy=continue`, push results
  to `results/<round>/`, write `turns/PRO-TURN-NN.md`, give the owner the one-line prompt.

## 2026-09-27/28: no-harness baseline and the worker-prompt finding

- Ultra-hard lab projects (branch `owner/ultra-projects`: revenue, pipeline, backup, sync): simple
  pipeline 4/6 + 2/2 sync, full 5/6 + 2/2, plain `codex exec` Astra high (no harness) 8/8.
- Diagnosis (results/diag-r1..diag4 in the private repo): the triage-paraphrased acceptance criteria in
  the worker prompt caused the in-harness misses (and workers rewrote the contract to fit). On
  identical code: original prompt 1/8, criteria as hints 6/8, no criteria 8/8 = raw.
- Decided and built: D023 (PR #4, `owner/request-authoritative`): request authoritative, no triage
  criteria in worker/oracle prompts, spec judge always judges the task as written, triage never invents
  requirements, contract-edit guard. Separate fix PR #5 (`owner/notify-failures`): ntfy retries and
  visible failures. Neither is merged; the owner merges.
- Overnight results (2026-09-28, private repo results/*, brief in results/MORNING-BRIEF-20260928.md):
  aa simple + D023 8/8 in 8.9 min (= plain Astra 8/8); aa full + D023 3/4 in 19.7 min (its spec judge
  handed back a correct delivery over a real, untested ambiguity); Luna first (aa cascade) 3/8 and plain
  Luna 2/8: Luna always passed the visible checks, so aa never escalated. Cheap-first needs difficulty
  routing or a stronger trigger than failed checks.
- Lab tooling: `~/ho04-private` (round scripts, notify.py with delivery check, monitors). ntfy: phone
  user `phone` (read agenticarch, write agenticarch-replies); the lab listens on the reply topic for
  messages starting `lab:`. ntfy rate-limit exemption for 127.0.0.1 and the Docker gateway 172.17.0.1.
- 2026-09-28 morning, owner decisions: I reviewed (independent subagent), fixed and merged PR #4 (D023),
  PR #5 (ntfy) and PR #6 (D024: simple pipeline by default, full-pipeline stages opt-in, Codex memories
  off for workers) into `m1-working-runtime`; aa-daemon restarted on it. The owner delegated PR review
  and merges into this branch; `main` stays the owner's.
- Round A (local model as worker): aa-gemma runs with a reversible systemd drop-in
  (`~/.config/systemd/user/aa-gemma.service.d/round-a.conf`: tool calling, gemma4 reasoning parser, 128k
  context, 2 sequences, 62% GPU); Codex uses it per call via `~/ho04-private/local-a/codex-local.sh`
  (custom provider on 127.0.0.1:8100, Responses API). Results in the private repo `results/local-a-r1`.
  Pro turn 04 (`turns/PRO-TURN-04.md`) is with the owner.

## 2026-09-28 afternoon and evening

- Merged into `m1-working-runtime` (owner-delegated review and merge):
  - PR #7/#8: local-first lane, off by default (D025);
  - PR #9: configurable tier lanes (D026);
  - PR #10: retry of the Claude login-refresh race;
  - PR #11: GPT-6 Luna always at high effort (D027).
- Rounds, all in the private repo `results/`:
  - round-b-r2: free local model first with a Luna review. 21/24 vs lean 20/24, no quota saving, 7x slower.
  - round-c-r2: Claude Opus 5.5 as the cheap worker. 23/24 vs Luna 21/24, equally fast; shifts Codex use to Claude.
  - round-d-r2: Jev pre-screen before the Opus review. Running at handoff.
- Decision models (Jev by TypeSafe, a paid API):
  - Jev is allowed for offline tests and lab rounds only, not the runtime.
  - The key is in `~/.config/typesafe/key`; a reseller key from jevtypesafeai.com was rejected.
  - Results:
    - jev-probe-r1 / jev-revisit-r1: Jev far better calibrated than SemIf.
    - jev-calib-r1: on real diffs, 0.9 skips only 12% of reviews.
- Owner tools:
  - The shared ntfy channel for all projects (topics `agents` / `agents-replies`).
  - `agent-notify`, `agent-replies` and `agent-channel`, with per-chat channel numbers: this lab chat is channel 1, the Mac Codex chat is channel 2.
  - The notify-owner skill for Claude Code and Codex; source in the private repo under `tools/agent-notify`.
- Test ledger page for others: https://claude.ai/artifact/J4cnLpvFFDL77HMQdAF4BK (generator in the private repo `research/harness-opt-01/effort/`).
- Round E is prepared, not started:
  - Mealie (FastAPI + Nuxt) is cloned in `~/lab-e/mealie`.
  - Backend and frontend tests run; python-ldap needs `sudo apt install libldap2-dev libsasl2-dev`, a lab stub is in place until then.
  - Arms: planner split plus Jev routing, vs planner routing. Specs and hidden exams still to write.

## 2026-09-29 night and morning

- PR #12 was merged (D028): Claude Opus 5.5 high builds routine and bounded tasks, failed passes go to Astra, and the
  review (`spec_check`) stays off by default. The daemon was restarted on it.
- Rounds, all in the private repo `results/`:
  - round-d-r2: the review added no correctness (20/24 with it, 21/24 without).
  - round-e-r1/r2: on Mealie, one Opus 5.5 high call built each spec alone, 4/4 correct in 13.3 min. That is as
    correct as the split-and-route runs and faster.
  - file-choice-r1: one multiple-choice question beats per-file yes/no (Jev 0.60, SemIf 0.47 MRR).
  - confidence-r1 / grading-prompts-r1: Opus's confidence from the diff alone does not flag wrong deliveries. With
    the project readable it did on the one pair tested. A re-run on all 63 deliveries is proposed, pending the owner.
  - semif-ft-r1: SemIf trained locally with LoRA on git-history labels reaches Jev (0.60 test MRR).
    - Run 2 (4B, 16 repos) finishes on its own: unit semif-r2-finish scores it, restarts `aa-gemma` and pings
      channel 1.
    - Run 3 (Qwen3.5-9B) is on hold for the owner.
    - The trained adapter is not deployed into aa: that needs an owner decision.
- `aa-gemma` was paused for training (owner approved) and is restarted by the finish script.

## 2026-09-30 and 2026-10-01

- **Merged into `m1-working-runtime`:**
  - PR #13, D029: an opt-in confidence check after the checks; a low score hands the work to Claude Fable 5.1 high, and
    a deep case follows if it is still low.
  - PR #14: the lab counts subscription use by the lane's CLI.
- **Merged later (2026-10-01):** PR #15, D030. Builders return `assumptions`, and the delivery note and the Done
  message list them.
- **CLIs updated:** Codex 0.155.1 to 0.159.2 (GPT-6.1 Sol needs 0.159 or later) and Claude Code 2.1.282 to 2.1.285
  (Sonnet 5.5). aa's subscription checks pass with both.
- **Rounds (private repo `results/`):**
  - round-f-r1: the confidence check with a Fable rework, 24/24 vs 22/24, one task.
  - round-g-r1: six setups on 8 real Apache Superset fixes.
  - round-h-r1: GPT-6 Astra, GPT-6.1 Sol and Claude Opus 5.5 alone on 20 Superset fixes: 7/7/5 correct, not
    distinguishable.
  - ask-r1: aa asks only when a value is missing outright; its other guesses are invisible to the owner, which is why
    PR #15 exists.
- **Strategy after a literature review of about 40 studies:** no more broad rankings of setups. Instead, defaults based
  on the literature, a small regression suite, and workflow tests.
- **Lab tools (private repo `research/harness-opt-01/lab-tools/`):**
  - `labkit.py`: step checkpoints.
  - `lab.py`: start, pause and resume; `lab-resume.service` restarts runs after a reboot.
  - `regress.py` with `regression-suite.json`: 13 discriminating tasks.

## 2026-10-02

- **Decisions:**
  - D031: no Sol lane; the decider keeps Astra and Opus.
  - D032 (PR #16): a research phase is offered once per new repository (young AND small) before the first build.
    - The owner replies `research <id>` or `noresearch <id>`.
    - The research call alone may use web search and fetch.
  - D033 (same day, amends D032): the owner decides on research. Use `aa task --research` or the reply
    `research <id>` before the build starts; the automatic offer is off by default.
- **Dropped by the owner:** prompt rewriting; a Codex fork; a separate private Codex installation and
  local prose models as harness parts.
- **Lab: Claude Code workflows (private repo `results/workflow-g6-r2`).**
  - Headless limit: `claude -p` waits at most 10 minutes for background work, such as a workflow, after the main
    agent's turn. Then it forces the final answer and the workflow is cut off.
  - Fix: set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` and tell the main agent to end its turn and wait. Verified with
    a 12-minute test.
  - With that fix, a workflow of Opus 5.5 agents on 6 of the 12 Superset fixes no single builder solved: 0/6
    strict, 1/6 under the round's preregistered test exclusions (corrected after GPT-6 Pro's turn 05 review).
    - 38% of required tests vs 32% for Opus alone.
    - About 3.4x the cost and 2.7x the time.
  - Workflows are not added to aa.
- **Lab: SemIf file hints (private repo `results/semif-hints-r1`).** Training with a "none of these files" option,
  shaped like the hint tournament. Running; not deployed.

## 2026-10-04

- D034 (this PR): Codex workers use a named permission profile with credential stores denied; the legacy -s flag is
  gone (`workers.codex_sandbox = "legacy"` restores it).
- Lab results (private repo):
  - hint3-r1: injected file hints do not measurably help Astra builders, and learned hints add nothing over text
    search. The owner accepted "no injected hints" and closed the hint track.
  - Clef-Flash is a candidate decider for factual checks only (Pro 06A).
- Claude's Bash sandbox cannot start on this Ubuntu host (AppArmor unpriv_bwrap vs Claude's seccomp helper). It fails
  closed. Lab builders are therefore Codex.

## Next steps

1. Continue HO-01 as above; then decide defaults (possibly minimal pipeline + proven gates).
2. First real deep case against a GitHub target repo (owner pastes the Pro prompts).
3. Install skills on the Mac (`tools/install_skills.py`).
4. Optional owner actions: `sudo efibootmgr -o 0002,0000` (boot Linux by default; firmware
   currently boots Windows first), `sudo apt install ipmitool` (fan readings via the BMC). Linger is already on.

## Sandbox

`~/dev/aa-sandbox` is a local test repo used for the live smoke tests.
