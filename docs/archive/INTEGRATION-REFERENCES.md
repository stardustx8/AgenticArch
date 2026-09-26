# Integration reference map

The versioned [research registry](../config/research-evidence.json) contains canonical references and dated caveats. Follow the specific primary interface, not a social summary.

| Component | Reference | Qualification requirement |
| --- | --- | --- |
| CLM | S17, pinned source; `src/clm/schema.py` and `server.py` | Exact head/encoder/tokenizer, loopback binding, no truncation, no mock, wire normalization |
| Pi | S18, pinned extension declarations | Actual model/effort readback, abort before request, supported subscription route |
| Codex adaptive reasoning | S19 and S20 | Native checkpoint, settings capture and acknowledgment, cancellation and compaction tests |
| OpenAI subscription execution | S02 and S03 | ChatGPT login and effective quota observer, no API key/paid spillover |
| Claude workers | S04, S05 and S09 | Unmodified authenticated Claude Code, permitted billing and actual effort |
| Pro web | S13 and S21 | Visible required product, exact same-case chat, manual handoff while automation unqualified |

API documentation identifies model and wire semantics; it does not authorize API billing in this architecture. Repository catalog references do not establish actual local availability. Pin the observed installed versions and store sensitive inventory privately.
