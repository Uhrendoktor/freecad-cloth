# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The supervisor has completed the required audit pass over all open PRs and open issues before starting the next implementation slice. The stale PR set (#292, #296, #299, #300, #303, #304, #306) was reviewed; each proposal was retained in the roadmap/issues and the diverged branch was closed rather than merged. No additional GitHub Actions workflow is permitted.

Current supervisor implementation branch: `agent/supervisor-sewing-gui-registration-20260830`.

## Replanned release sequence

The roadmap remains a vertical-slice release plan, but the immediate order is now:

1. **P0-0 Sewing GUI registration recovery (#308):** make command groups complete, deterministic and idempotent; make workbench icon resolution robust; prove all public Sewing commands exist during real FreeCAD activation.
2. **P0-1 DrapeTarget authority (#276/#289/#284):** make target-neutral collision state authoritative and recompute-safe, including explicit stale status and refresh lifecycle.
3. **P0-2 canonical garment E2E (#278/#155/#143):** prove Pattern -> Sewing -> fitting/arrangement -> Simulation -> save/reload -> upstream edit/invalidation -> rebuild/re-simulate through public workbench UI.
4. **P0-3 simulation behavior (#145/#159/#161):** verify quality/material/collision controls materially affect generated topology/backend parameters and persist through save/reload.
5. **P0-4 release UX/persistence audit:** remove remaining scripting-only paths and verify toolbar/menu/task-panel/selection/undo/recompute behavior.
6. **P1 authoring/export/package:** implement only concrete Pattern parity blockers from #162, then production 2D export (#147/#163), examples and packaging.
7. **P2 optional solver benchmark (#148):** only after P0/P1 are green.

## Research decisions

Recent CLO/Marvelous Designer research confirms that the release-critical interaction model is:

- semantic sewing with Segment, Free, 1:N and M:N relationships;
- visible directional correspondence, length mismatch feedback and reversal/repair;
- arrangement points/bounding volumes and persistent placement controls before draping;
- particle distance as a behavior-changing quality control rather than a cosmetic preference;
- native property/task-panel editing as a first-class workflow surface.

FreeCAD research confirms that Sketcher already supplies the needed geometric/dimensional constraint solver, external geometry and expressions; Part/OCCT provides curve/offset geometry; TechDraw/Draft provide native SVG/DXF production paths. Cloth should remain the semantic layer rather than duplicating these kernels.

## Current implementation slice

`InitGui.py` now derives Sewing registration completeness from the actual command constants and rejects missing/extra groups with a diagnostic. The Sewing group explicitly contains `Repair Seam`, and workbench icons resolve to repository-local absolute paths while the normal FreeCAD icon path remains registered.

The static GUI contract now checks all public Sewing command groups and all three workbench icons. The real FreeCAD/Xvfb screenshot scenario now asserts the complete Sewing command set at workbench activation, so a registration mismatch fails before later screenshots can be mistaken for acceptance.

## Architecture gates

- **P0-A Pattern:** native Sketcher geometry remains the editable geometry authority; Cloth owns semantic pattern metadata.
- **P0-B Sewing:** semantic references, curved correspondence, M:N sewing and repair UX are the persistent sewing authority.
- **P0-C Human fitting:** persistent anthropometric mannequin and arrangement model are FreeCAD document state.
- **P0-D Drape target:** target-neutral mannequin/FreeCAD geometry collision input is authoritative and persistent.
- **P0-E Simulation:** deterministic mesh/solver is disposable derived state; lifecycle controls expose stale/ready/running/error states.

## Coordination rules

- Update this file at start/handoff of each implementation slice.
- Never create another workflow; reuse `canonical-execution.yml`.
- Never silently retarget semantic references after topology changes.
- Public FreeCAD workbench commands/task panels/document objects are the acceptance surface; utility-only tests are insufficient.
- Do not merge a branch merely because its feature is useful if it is stale or non-mergeable; re-cut from current main and preserve the proposal in the issue/roadmap.
- A milestone is not complete until canonical CI is green and merged-main verification is green.
