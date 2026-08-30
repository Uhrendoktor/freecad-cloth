# Cloth Workbench Agent Status

Last updated: 2026-08-30

## Supervisor state

The roadmap was re-audited against the current mainline, open PRs/issues, and current CLO/FreeCAD behavior. The release target remains three native FreeCAD workbenches working as one document workflow; utility-only scripts are not a completion criterion.

Open PR audit before this slice:
- **#291** — verification-only sewing task-panel PR explicitly said not to merge; closed with that reason.
- **#290** — stale DrapeTarget repair was substantive but diverged from current main and relied on a runtime monkey-patch without canonical acceptance evidence; its intent is being reimplemented on a fresh branch with explicit regression coverage.

Current supervisor branch: `agent/supervisor-replan-stale-target-20260830`.

### Replanned release sequence

1. **P0-D/P0-E target-authoritative simulation:** stale DrapeTarget must never break document recompute; Simulation status must expose the exact stale reason; Step/Run must refuse until Refresh; save/reload must preserve the target contract.
2. **P0-B Sewing acceptance:** finish the public task-panel workflow for curved correspondence, reversal/alignment diagnostics and transactional M:N editing; verify with real FreeCAD/Xvfb.
3. **P0-A Pattern production minimum:** audit native Sketcher authority, semantic marks, seam allowances, stable references and downstream invalidation; add only missing release blockers.
4. **P0-C Human fitting:** keep the parametric mannequin as the default human target, but expose it through the same target-neutral collision contract as arbitrary FreeCAD geometry.
5. **P0 release fixture:** one public-workbench create → sew → arrange → drape → simulate → save/reload → edit/invalidate → refresh/rebuild → simulate scenario, with screenshots/logs as artifacts.
6. **P1 production UX:** consistent action hierarchy, terminology, icons, units, arrangement points and material/particle-distance presets.
7. **Release follow-up:** DXF/SVG/TechDraw export, packaging/examples/docs; optional native solver benchmarks remain non-blocking until the end-to-end release gate is green.

### CLO-derived behavior that is now release-relevant

- Segment and free sewing are separate user gestures; M:N is a first-class sewing workflow.
- Sewing direction/reversal and length mismatch need visible diagnostics, not silent correction.
- Arrangement points/bounding volumes are a distinct fitting concept from arbitrary 3D Placement.
- Particle distance is the primary quality/performance control; working meshes are coarse and final meshes are finer.
- Avatar skin offset and collision thickness are separate controls from cloth mesh density.

### Architecture gates

- **P0-A Pattern:** native `Sketcher::SketchObject` is the geometry authority; PatternIR remains solver-neutral.
- **P0-B Sewing:** persistent semantic references, curved correspondence, M:N sewing and repair UX; canonical verification remains required.
- **P0-C Human fitting:** persistent anthropometric mannequin and collision provider are implemented; target-neutral integration remains the authoritative path.
- **P0-D Drape target:** persistent target-neutral DrapeTarget supports mannequin and arbitrary FreeCAD Shape/Mesh; stale state is explicit and refreshable.
- **P0-E Simulation:** deterministic mesh/solver and lifecycle/status controls exist; release blocker is safe stale-target lifecycle plus canonical E2E verification.

### Active workstreams

| Workstream | Issue | Status |
|---|---:|---|
| DrapeTarget authority | #276/#289 | **in progress — supervisor repair** |
| Canonical garment E2E | #278 | queued behind target lifecycle |
| Curved sewing repair acceptance | #275 | implementation merged; canonical verification pending |
| Pattern authoring production minimum | #162 | active audit; no duplicate drafting kernel |
| Simulation quality/materials | #145 | active P0 integration |
| UI consistency | #267 | queued behind functional release gates |
| Export/package/install | #163/#147 | release follow-up |

### Coordination rules

- Update this file at start/handoff of each implementation slice.
- Reuse `.github/workflows/canonical-execution.yml`; never create a duplicate workflow.
- Public FreeCAD commands, task panels and document objects are the acceptance surface.
- Do not silently retarget semantic references after topology changes.
- Compatibility shims may exist during migration, but they must not become a second source of truth.
