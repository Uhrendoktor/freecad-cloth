# FreeCAD Cloth repository guidance

Use `AGENTS.md` as the primary repository instruction contract.

Architecture:
- FreeCAD document persistence and native geometry are authoritative.
- Cloth domain objects own garment meaning.
- Derived meshes, collision data and solver state are rebuildable.
- PositionBasedDynamics is the production runtime solver.
- `docs/ARCHITECTURE.md` and `docs/PROJECT_STRUCTURE.md` define the detailed boundaries.

Current state:
- Verify the current branch HEAD before making state claims.
- Treat `AGENT_STATUS.md` and `TOOL_STATE.md` as coordination snapshots, not architecture authority.
- Treat issues, PRs and CI artifacts as task-local evidence.

Execution:
- Use `.github/workflows/canonical-execution.yml` as the canonical acceptance path.
- Do not add parallel workflows or parallel document/domain models.
- For simulation work, also read the nested simulation agent instructions.
