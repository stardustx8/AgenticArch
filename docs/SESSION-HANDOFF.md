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

1. First real deep case against a GitHub target repo (owner pastes the Pro prompts);
   fix whatever the live Pro connector behaviour reveals (marker files, branch names).
2. Install skills on the workstation (`~/.codex/skills`) and the Mac; verify the Codex
   desktop app picks up `agenticarch`.
3. Codex fork (openai/codex at the installed 0.155.x) with an Astra-Ares-style
   pre-generation checkpoint calling CLM; used only by worker `codex exec`.
4. After ~100 logged tasks: fine-tune the CLM head on `decisions` (owner picks = labels).
5. Optional: `sudo loginctl enable-linger rosh` so units run without a login session.

## Sandbox

`~/dev/aa-sandbox` is a local test repo used for the live smoke tests.
