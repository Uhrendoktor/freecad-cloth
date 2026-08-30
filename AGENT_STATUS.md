# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

P0 supervision is focused on making the public FreeCAD Pattern -> Sewing -> Simulation workflow authoritative end-to-end. Before each implementation slice, open PRs and active issues are re-audited and subagent proposals are incorporated. The canonical CI workflow is reused; no duplicate workflow is permitted.

Current supervisor implementation branch: `integration-audit-20260830-v2`.

### Integration audit result

The mainline audit found two integration defects in the DrapeTarget/Simulation seam and one compatibility-link contract defect. These are fixed on the audit branch and submitted as PR #303. The canonical end-to-end release scenario remains tracked by #278 and must be the acceptance gate before release.

Fixed in integration layer:
- GUI DrapeTarget creation no longer routes through the legacy `AvatarProxy` setter or changes the target type to `Mannequin`.
- `ClothDrape_RefreshTarget` is a public Simulation-workbench command; the simulation panel exposes target state and refresh.
- Simulation Step/Run are disabled while the DrapeTarget is stale/unbuilt and the command layer rejects stale execution.
- `set_avatar_collision_source()` again returns the compatibility `AvatarProxy`, so `AvatarProxy`/`CollisionProxy` document links do not accidentally point to `DrapeTarget`.

Out of integration scope:
- Pattern validation/native Sketcher validation is implemented by open PR #300; do not duplicate that feature in the integration slice.
- Seam-repair broad exception handling is tracked in issue #301.
- The complete public-workbench journey is the explicit release gate in #278; current canonical `tests/freecad_e2e.py` does not yet cover validation, avatar arrangement, DrapeTarget refresh, or the full stale-target loop.

## Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is geometry authority; PatternIR is solver-neutral.
- **P0-B Sewing:** semantic references, curved correspondence, M:N sewing and repair UX are implemented; canonical verification remains required.
- **P0-C Human fitting:** persistent anthropometric mannequin and collision provider are implemented and previously smoke-tested.
- **P0-D Drape target:** persistent target-neutral DrapeTarget is authoritative for simulation collision input; `AvatarProxy` remains compatibility/migration state only.
- **P0-E Simulation:** deterministic mesh/solver and lifecycle/status controls exist; stale target execution is now blocked at both command and task-panel layers.

## Active workstreams

| Workstream | Issue | Status |
|---|---:|---|
| Integration audit | #278 / PR #303 | **in progress — canonical CI pending** |
| DrapeTarget authority | #276 | implementation landed; integration repair submitted in #303 |
| Canonical garment E2E | #278 | **release blocker — journey coverage incomplete** |
| Curved sewing repair acceptance | #275 | merged implementation; canonical verification pending |
| Seam repair exception diagnostics | #301 | open; feature-scope follow-up |
| Pattern authoring production minimum | #162 | active audit; avoid duplicate drafting kernel |
| Pattern native validation | #300 | open PR; required before validation step can be accepted on main |
| Simulation quality/materials | #145 | active P0 integration |
| Export/package/install | #163/#147 | release follow-up |

## Coordination rules

- Update this file at start/handoff of each implementation slice.
- Do not create another GitHub Actions workflow.
- Do not silently retarget semantic references after topology changes.
- Public FreeCAD commands/task panels/document objects are the acceptance surface; utility-only tests are insufficient.
- Keep compatibility shims only where they do not remain authoritative.
