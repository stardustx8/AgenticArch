# Session handoff

Updated 2026-09-25 (Claude Code session on the workstation, branch `m1-working-runtime`).

## State

The `aa` runtime is installed and running on the workstation (see
[IMPLEMENTATION-STATUS](../IMPLEMENTATION-STATUS.md) for what was verified live). Owner
decisions are in [OWNER-REQUIREMENTS](OWNER-REQUIREMENTS.md) v3 and DECISIONS D011-D015.

Setup done this session: GitHub SSH key (`~/.ssh/id_ed25519_github`), Claude Code CLI
(Max login), uv + CLM venv (vLLM 0.30, contrastive-lm), CLM head download, Qwen3-8B,
ntfy (rootless Docker) + Tailscale forwarder, systemd user units, `~/.config/agenticarch/aa.toml`.
The private case repo stardustx8/GPT-Pro-Escalation is reachable and empty until the
first case initializes it.

## Next steps

0. Open PR: https://github.com/stardustx8/AgenticArch/pull/2 (review/merge by owner).
   Candidates still open (eval/PROBES.md): SemIf secret gate, worker status field.
   Done this session: spec-check loop (D017), Claude guard (D018), failure triage (D019).
   Codex 401s on 2026-09-26 night resolved after the desktop app refreshed the shared login.
1. (Done: triage policy = Codex decides.) Owner decision: triage policy — Codex alone, or Codex + SemIf with ask-on-disagreement
   (~20% pings) or take-higher-if-1-apart (~6% pings). Data: eval/RESULTS.md.
2. First real deep case against a GitHub target repo (owner pastes the Pro prompts).
3. Install skills on the Mac (`tools/install_skills.py`).
4. Re-run `tools/eval_decisions.py` on the owner's logged real tasks.
5. Optional: `sudo loginctl enable-linger rosh` so units run without a login session.

Decided 2026-09-25 (second session): SemIf replaces CLM (D016); no Codex fork, model-only
switching (D015). SemIf model copied from the SHARED archive to
`~/.local/share/agenticarch/semif/` (sha256 verified), served by `aa-semif`.

## Sandbox

`~/dev/aa-sandbox` is a local test repo used for the live smoke tests.
