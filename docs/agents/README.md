# AI agent documentation and guidelines

This section contains material specific to AI-agent workflows or agent-produced evidence. It is intentionally separate from the human FreeCAD user manual and human software developer documentation.

## Authoritative instructions

- [Agent workflow guidelines](WORKFLOW_GUIDELINES.md) — current-state-first execution, bounded task prompts, review discipline, and state-file hygiene.

- [Repository-wide agent contract](../../AGENTS.md) — primary instructions, source-of-truth precedence, task scope, and verification.
- [Copilot instructions](../../.github/copilot-instructions.md) — repository guidance for GitHub Copilot.
- [Path-specific instructions](../../.github/instructions/) — narrower rules for simulation code and workflow files.
- [Agent observation bundles](AGENT_OBSERVATION_BUNDLE.md) — schema and purpose for indexing evidence already produced by a FreeCAD batch run.

If documents conflict, follow the precedence defined in the root `AGENTS.md`. This page is an index, not a second instruction hierarchy.

## Keep audiences separate

Common development, test, architecture, and contribution procedures are maintained under [Developer documentation](../developers/README.md). Task-level progress and decisions belong in the governing GitHub issue or pull request, not in permanent agent-only status documents. User task instructions belong under [FreeCAD user documentation](../users/README.md).
