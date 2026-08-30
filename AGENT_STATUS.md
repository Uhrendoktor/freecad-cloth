# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

P0 supervision is focused on making the public FreeCAD Pattern -> Sewing -> Simulation workflow authoritative end-to-end. Before each implementation slice, open PRs and active issues are re-audited and subagent proposals are incorporated. The canonical CI workflow is reused; no duplicate workflow is permitted.

Current supervisor implementation branch: `agent/fix-python312-sewingcommands-20260830`.

### Current plan

1. Fix the canonical Python test blocker without removing Python 3.12 from the support matrix.
2. Verify the headless Sewing command import contract across Python 3.10/3.11/3.12 and run the complete Python suite.
3. Hand off through a PR for canonical FreeCAD/Xvfb verification.
4. Continue DrapeTarget authority work (#276) only after canonical CI is green.

## Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is geometry authority; PatternIR is solver-neutral.
- **P0-B Sewing:** semantic references, curved correspondence, M:N sewing and repair UX are implemented; canonical verification remains required.
- **P0-C Human fitting:** persistent anthropometric mannequin and collision provider are implemented and previously smoke-tested.
- **P0-D Drape target:** persistent target-neutral DrapeTarget is implemented for mannequin and arbitrary FreeCAD Shape/Mesh. **Next work: make Simulation consume it directly.**
- **P0-E Simulation:** deterministic mesh/solver and lifecycle/status controls exist. **Current blocker remains target-authoritative collision rebuild after CI recovery.**

## Active workstreams

| Workstream | Issue | Status |
|---|---:|---|
| Python 3.12 canonical CI regression | #293/#294 | **in progress — headless SewingCommands import contract** |
| Sewing GUI registration recovery | #308 | **in progress — PR #314; implementation complete, canonical check suite currently failed before jobs were created** |
| DrapeTarget authority | #276 | queued behind CI recovery |
| Canonical garment E2E | #278 | queued after target authority |
| Curved sewing repair acceptance | #275 | merged implementation; canonical verification pending |
| Pattern authoring production minimum | #162 | active audit; avoid duplicate drafting kernel |
| Architecture: Sketcher/Cloth boundary | #165 | **claimed — native Sketcher edge authority for Sewing references** |
| Simulation quality/materials | #145 | active P0 integration |
| Export/package/install | #163/#147 | release follow-up |

## CI regression finding

The failing `test_sewing_repair.py` assertion is not Python-version-specific: the same `AttributeError` was reached under Python 3.10 and 3.12 in canonical run `33309390274`. `SewingCommands._ACTIVATION` was defined inside the optional `import FreeCADGui` registration block, so headless CPython imports omitted a public module-level contract that the regression test intentionally checks. The fix keeps `_ACTIVATION` available independently of GUI registration while retaining optional FreeCADGui command installation.

## Coordination rules

- Update this file at start/handoff of each implementation slice.
- Do not create another GitHub Actions workflow.
- Do not silently retarget semantic references after topology changes.
- Public FreeCAD commands/task panels/document objects are the acceptance surface; utility-only tests are insufficient.
- Keep compatibility shims only where they do not remain authoritative.
