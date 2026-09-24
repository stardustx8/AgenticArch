# Integration references

Primary references inspected on 2026-09-24. They support integration discovery, not claims that any capability has been exercised in the owner's environment. Recheck the installed client and current interfaces before coding an adapter. Model names in the routing policy express the requested configuration; actual IDs are discovered, never fabricated.

| Source | What it establishes | What it does not establish |
| --- | --- | --- |
| [OpenAI: Build skills](https://developers.openai.com/codex/build-skills) | Skill folders use `SKILL.md` with name/description; optional scripts/references; local discovery roots | Availability or contents of a particular custom skill |
| [OpenAI: Computer Use](https://developers.openai.com/codex/computer-use) | macOS/Windows UI capability and permission boundaries; explicitly excludes ChatGPT self-automation | A permitted automatic Pro web submission path or Linux support for this feature |
| [OpenAI: configuration reference](https://developers.openai.com/codex/config-reference) | Model/effort configuration depends on client/model support | Enforcement by prose alone or the right ID for a local installation |
| [OpenAI: non-interactive mode](https://developers.openai.com/codex/noninteractive) | `codex exec`, JSONL events, output schemas and explicit session resumption | That all desktop tools are available in a CLI worker |
| [SemIf upstream](https://github.com/TheoLeeCJ/SemIf) | Local typed option scoring; JSONL CLI shape; direct and reuse backends; workload calibration caveats | A stable HTTP endpoint, universal correctness confidence, or the owner's installed revision |
| [Anthropic: Claude Fable](https://www.anthropic.com/claude/fable) | The named model family and provider | Which version/transport/auth the local challenge skill uses |

A publication's benchmark is not an AgenticArch benchmark. No fixed subscription price, unlimited capacity, coding-task distribution, success rate, latency guarantee or savings claim is part of this design. SemIf's own benchmark/calibration results do not validate coding-loop decisions automatically.

No upstream code or model weights are bundled. A local integration must honor its pinned dependency and model licenses; inspect those exact versions before distributing dependencies.

Additional current model references: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) documents supported effort values; this project intentionally permits only low/high. [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) documents high effort; the owner's Pro web lane is separate. [GPT-6 Astra announcement](https://openai.com/index/gpt-6-astra/) describes a Pro product variant, but account/UI identity must still be verified. API IDs do not themselves select a ChatGPT web mode.

**Compatibility observation:** the current Luna model page states that Chat Completions function calling requires effort `none`; that conflicts with this project's Luna low/high policy for tool-using coding workers. Use a supported Responses/Codex tool path and verify the actual custom provider adapter. Do not silently change effort to none or omit tools.
