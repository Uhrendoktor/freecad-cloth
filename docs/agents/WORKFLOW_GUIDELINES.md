# AI agent workflow guidelines

These repository-specific guidelines supplement the root [`AGENTS.md`](../../AGENTS.md), which remains the authoritative instruction contract. Follow the root contract whenever guidance differs.

## Agent execution contract

Before changing code, verify the target branch HEAD and read only the canonical documentation relevant to the requested change. Inspect a governing issue/PR only when its number is known or the task is explicitly about its work.

Do not enumerate the repository's entire issue/PR history. Do not ingest all open issues or PRs because they are linked from a task. Closed issues, merged PRs, old branches, historical runs and artifact archives are not current context.

When a task depends on a live coordination issue, use the current issue body as the coordination summary and inspect child issues only for the specific hypothesis being tested. Do not treat historical child-issue prose as implementation authority.

Re-cut implementation branches from the current target HEAD. Before merge: inspect the diff and changed files, verify terminal-green CI for the exact head, merge, verify the merge, then delete the source branch when permitted.

When an issue is closed, use an explicit GitHub state reason (`completed`, `duplicate`, or `not_planned`) and record the reason in the issue conversation. Do not close an unresolved engineering problem merely to reduce queue size.

## Task prompt contract

For non-trivial agent work, use the seven-field prompt contract in the root `AGENTS.md`. That file is the canonical prompt schema; this document defines the execution behavior around it.

Keep prompts bounded, omit historical conversations and large logs, and give links or identifiers so the agent can inspect only the relevant evidence.

## Agent state

Keep `AGENT_STATUS.md` and `TOOL_STATE.md` compact. They are current-state summaries, not historical experiment logs.

The human development environment, CI gates, and contribution procedures are described in the [developer guide](../developers/DEVELOPMENT.md).
