# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

P0 supervision is focused on making the public FreeCAD Pattern -> Sewing -> Simulation workflow authoritative end-to-end. Before each implementation slice, open PRs and active issues are re-audited and subagent proposals are incorporated. The canonical CI workflow is reused; no duplicate workflow is permitted.

Current supervisor implementation branch: `agent/drapetarget-authority-20260830`.

### Current plan

1. Make `DrapeTarget` the authoritative simulation collision input; retain `AvatarProxy` only as compatibility/migration state.
2. Ensure target changes rebuild the collision surface deterministically and expose the rebuild reason.
3. Add/extend focused regression coverage, then hand off through a PR for canonical FreeCAD/Xvfb verification.
4. In parallel, keep #275 and #278 scoped to public-workbench acceptance rather than utility-only tests.
5. After P0 simulation authority is green, close the remaining Pattern/Sewing release gates and only then pursue packaging/export and optional solver benchmarking.

## Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is geometry authority; PatternIR is solver-neutral. **Production slice hardened 2026-08-30:** one-way authority contract, versioned semantic IDs, fail-closed topology deletion, and save/reload regression coverage.
- **P0-B Sewing:** semantic references, curved correspondence, M:N sewing and repair UX are implemented; canonical verification remains required.
- **P0-C Human fitting:** persistent anthropometric mannequin and collision provider are implemented and previously smoke-tested.
- **P0-D Drape target:** persistent target-neutral DrapeTarget is implemented for mannequin and arbitrary FreeCAD Shape/Mesh. **Current work: make Simulation consume it directly.**
- **P0-E Simulation:** deterministic mesh/solver and lifecycle/status controls exist. **Current blocker: target-authoritative collision rebuild.**

## Active workstreams

| Workstream | Issue | Status |
|---|---:|---|
| DrapeTarget authority | #276 | **in progress — supervisor** |
| Canonical garment E2E | #278 | queued after target authority |
| Curved sewing repair acceptance | #275 | merged implementation; canonical verification pending |
| Pattern authoring production minimum | #162 | active audit; Sketcher authority slice hardened; remaining UX/parity follow-ups scoped in architecture doc |
| Simulation quality/materials | #145 | active P0 integration |
| Export/package/install | #163/#147 | release follow-up |

## Coordination rules

- Update this file at start/handoff of each implementation slice.
- Do not create another GitHub Actions workflow.
- Do not silently retarget semantic references after topology changes.
- Public FreeCAD commands/task panels/document objects are the acceptance surface; utility-only tests are insufficient.
- Keep compatibility shims only where they do not remain authoritative.
