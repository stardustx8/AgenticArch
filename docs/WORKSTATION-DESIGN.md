# Workstation-first integration

The owner reports a Linux AI workstation with a 96 GB RTX PRO 6000 Blackwell and 128 GB ECC host memory, running custom Codex with local and remote models. These are planning inputs, not a live inventory. Discover actual client revisions, GPU driver/runtime, free resources, installed skills and provider interfaces before changing them.

Keep the existing working Codex and Claude Code paths intact. Install experimental native checkpoint changes side by side with rollback. Maintain the Pi alternative through the same core policy and persistent state. Do not change global authentication, networking or permissions merely to make an adapter easier.

Run one pinned CLM encoder/head service. Bind both encoder and API to loopback, avoid automatic checkpoint downloads in steady state and disable unneeded UI/CORS. Measure memory with the real configured context and cache allocation. Limit optional local generation to one heavy helper initially; reserve interactive capacity and refuse jobs rather than killing unrelated work.

The runtime inventory must establish exact model identities and available effort controls, actual subscription login/billing, quota observation precision, sandbox permissions, cancellation, cache/compaction behavior and restoration of task/case sessions. Keep credentials, complete machine inventories and private paths out of the public repository. Commit only a sanitized capability/status summary.

CLM may improve context, diagnostics and evidence coverage. Extra generative agents, graph databases and broad best-of-N code generation are not mandatory. Qualify each optional helper with the decision-family and quota evaluations. A workstation with spare VRAM does not make an unmeasured architecture superior.

The first deliverable after local discovery is a narrow working loop using one qualified worker, real tests and durable recovery. Add peers, adaptive effort and deep-review automation only behind their own acceptance gates. See [implementation](IMPLEMENTATION-PLAN.md) and the two [harness packages](../README.md).
