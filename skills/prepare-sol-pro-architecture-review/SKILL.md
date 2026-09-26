---
name: prepare-sol-pro-architecture-review
description: "Start a GPT-6 Pro deep case for tough work (architecture, research, consequential design) through the AgenticArch coordinator: private case branch, one-line Pro prompt, Opus x Astra challenge rounds, Pro GO and implementation. Legacy identifier kept for compatibility."
---

# Start a GPT-6 Pro deep case

Use for tough work, architecture, research, security/migration/irreversible design,
or when the owner explicitly asks for Pro. The legacy name does not select Sol or
Astra Max; the anchor is GPT-6 Pro in ChatGPT web with the GitHub connector.

Read [protocol](references/protocol.md) for the full flow.

## Steps

1. Make sure the relevant local changes are committed (the case starts from HEAD and
   the coordinator pushes that commit as `aa/base-<case>` so Pro can read it). The
   target repo must have a GitHub origin the ChatGPT connector can access.
2. Write the task as the owner stated it, plus concrete acceptance criteria and known
   constraints. Separate facts from assumptions; do not invent requirements.
3. Queue it: `aa task --tier tough --repo <repo> "<task>"`.
4. The coordinator creates `case/<id>` in the private repo `stardustx8/GPT-Pro-Escalation`
   with BRIEF.md and PRO-TURN-01.md and sends the owner an ntfy push with a one-line
   prompt. `aa prompt <case>` prints it again. The owner pastes it into a NEW Pro chat
   (connector on) named `AA <case>`, and every later turn into that SAME chat.
5. From then on the daemon continues automatically; see fable-adversarial-review for
   the challenge rounds. Report the task/case id and the prompt; do not claim Pro has
   run until `aa status` shows the next phase.

No ZIP upload is needed: Pro reads the case branch and the target repo directly.
Never put secrets or unrelated private data into BRIEF.md or the case branch.
