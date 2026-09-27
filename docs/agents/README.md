# Development and Agent Documentation

This directory is the machine-oriented documentation layer for FreeCAD Cloth.

Its job is to make the repository safe to modify by autonomous or semi-autonomous agents without turning the project into a collection of session notes.

## Documentation layers

| Layer | Purpose | Authority |
| --- | --- | --- |
| README.md | Project orientation | High-level |
| docs/ | Engineering contracts and durable technical guidance | Authoritative |
| docs/agents/ | Agent execution rules and integration contracts | Authoritative for agent behavior |
| wiki/ | Polished human-facing usage documentation | Published user layer |
| AGENT_STATUS.md | Compact current coordination state | Current state |
| TOOL_STATE.md | Compact execution/tool state | Current state |

The human Wiki is not the engineering source of truth. It explains implemented behavior for users; implementation contracts stay in docs.

## Agent entry point

Before changing code:

1. Read docs/DEVELOPMENT.md.
2. Read docs/ARCHITECTURE.md for ownership and invalidation rules.
3. Read docs/PROJECT_STRUCTURE.md before adding modules.
4. Inspect the current GitHub issues, PRs and canonical workflow.
5. Read AGENT_STATUS.md and TOOL_STATE.md when the task involves ongoing coordination.

Before changing documentation:

- Update an existing authoritative document when the content is an engineering contract.
- Update wiki/ when the change is primarily user-facing.
- Keep human-facing prose factual and tied to implemented behavior.
- Prefer stable generated media from docs/screenshots for Wiki images.
- Do not create dated scratch documentation.

## Wiki bridge

wiki/ is the canonical source for the GitHub Wiki.

The bridge is implemented in tools/wiki_bridge.py and executed as a job inside the single canonical workflow:

- Publish: repository wiki/ to the GitHub Wiki Git repository.
- Import: GitHub Wiki to repository wiki/, followed by a normal pull request.

Agents should normally modify wiki/*.md in the repository. A merge to main publishes those pages automatically, provided WIKI_SYNC_TOKEN is configured.

Direct edits in the GitHub Wiki are treated as an external change. Use the manual import operation to pull them into a branch and review them before they are preserved.

See WIKI_BRIDGE.md for the exact credential, workflow and conflict contract.

## Agent principles

### Durable over conversational

The repository is the durable control plane. Issue and pull-request conversations are evidence and coordination, not the canonical design database.

### Explicit authority

FreeCAD owns document persistence and editable geometry. Cloth owns garment semantics. Solvers own derived physics state. Do not create a parallel persistence authority merely to simplify implementation.

### Fail closed

Invalid semantic references, stale derived state and incomplete prerequisites should be visible and actionable. Do not silently retarget user data or consume stale solver state.

### Small, verifiable changes

Keep implementation changes focused. Select the smallest verification that proves the change, then use the canonical workflow for the final acceptance path when the change touches GUI, persistence, simulation or CI.

## Change routing

| Change | Primary location | Typical verification |
| --- | --- | --- |
| Domain implementation | freecad_cloth/ | Focused unit or contract tests |
| FreeCAD UI | freecad_cloth/ plus tests | Real FreeCAD/Xvfb |
| Engineering contract | docs/ | Contract and documentation tests |
| Human usage prose | wiki/ | Markdown/source review |
| Wiki synchronization | tools/wiki_bridge.py plus canonical workflow | Python compile plus workflow review |
