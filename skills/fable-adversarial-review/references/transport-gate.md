# Pro web transport: capability and permission gate

## Verified boundary

As inspected on 2026-09-24, [OpenAI's Computer Use documentation](https://developers.openai.com/codex/computer-use) describes operating graphical applications on macOS/Windows and says the feature cannot automate ChatGPT itself. Consequently, **the standard Computer Use feature is not a verified implementation path for automatic ChatGPT submission in this kit**. Linux support, a custom Codex build, or an available browser tool alone does not overturn that restriction.

This is an important integration gap, not a reason to change the required Pro model. The initial deployable mode is human-assisted Pro web transport. All other packaging, repository synchronization, Fable invocation, evidence checks and checkpointing can still be automated where permitted. Human-assisted rounds remain explicitly labelled and are not marketed as unattended operation.

## Default behavior

`config/local.example.json` selects `manual` and marks automatic ChatGPT control unqualified. The skill prepares the approved ZIP, resolved prompt and exact attachment list. For the first round the owner uploads them to GPT-6 Pro and provides the conversation binding through private local state. For later rounds the owner submits the prepared continuation to that **same** chat. The coordinator verifies the returned contribution before moving on.

If the user or policy demands an entirely unattended run, fail preflight with `WAIT_CAPABILITY`; do not start a run which will later pretend to satisfy that requirement. Manual fallback requires willingness to perform the handoff, not a silent change of mode.

A manual report of model selection is recorded as human-attested, not machine-verified. The implementation may verify visible model selection by an allowed observation mechanism. It must never infer effective model identity from the response's self-description. Capability reports distinguish observed evidence, human attestation, and unverified claims.

## Conditional automation contract

Enable `supported_ui` only when a capability record proves all of the following for the actual target and interface:

1. Current product/platform guidance explicitly permits this ChatGPT web workflow, or an authorized supported integration provides it. Record exact source, version, date and scope. A self-edited boolean is not sufficient evidence.
2. The actual custom Codex environment exposes the required tool and supports its host OS, persistent authenticated browser, file upload, observation and cancellation.
3. The owner authorized the account, destination, data classes, content manifest and actions. No login, CAPTCHA, credential extraction or privilege expansion is automated.
4. A synthetic first send, duplicate/restart test, and same-chat continuation have passed. Tool/platform restrictions and required confirmation remain in effect.

Revalidate on tool, interface, account, OS or relevant policy changes. No bridge may use hidden endpoints, stolen/exported cookies, permission-bypass settings, a loopback proxy, a second browser, local vision, or another agent to evade the restriction. A genuinely separately supported integration must be evaluated on its own authorization and documented capabilities; it is not a presumed workaround.

## Browser protocol when qualified

Operate only the approved origin/account and exact stored case conversation. Before each send, verify the model selector identifies the owner's requested Pro mode and retain the visible selection receipt. Prepare a unique case/turn marker and outbox record, attach the approved immutable ZIP/delta, wait for readiness, submit once and verify that marker in the resulting message. Store the URL/session binding privately immediately.

After an ambiguous interruption, inspect existing messages before retrying. No blind resubmission, new-chat fallback, account rotation or rate-limit evasion. If the message cannot be reconciled, checkpoint and ask for human resolution. A disappeared spinner is not evidence of a complete response: require the expected artifact, end-of-turn receipt and repository readback.

## Model-name resolution

`GPT-6 Pro` is the owner's workflow label for the Pro model/mode in ChatGPT, not an invented API ID. Record the actual visible product label and verified mapping. A label such as a Pro variant of Astra must be verified through current official guidance and the owner's model selector; do not infer equivalence from a substring. Ordinary Astra high or max is not a substitute for the Pro web lane. Runtime model controls stay outside the task prompt.
