# CLO-style feature matrix and FreeCAD workbench priority

Supervisor research snapshot: 2026-08-31.

## Product boundary

The goal is a FreeCAD-native garment workbench with a CLO-like interaction model, not a clone of CLO's internal architecture. FreeCAD owns editable geometry and document persistence; Cloth owns garment semantics; the solver owns physics. No feature in this matrix should create a second geometry kernel, scene graph, solver, or persistence authority.

## Workflow feature matrix

| Capability | Prototype | MVP | Production | Authority / boundary |
| --- | --- | --- | --- | --- |
| Native Sketcher pattern geometry | Required | Harden | Maintain | Sketcher -> PatternPiece |
| Semantic seam object | Required | Harden | Maintain | Cloth SewingGraph |
| Segment sewing | Required | Harden | Maintain | SewingGraph |
| Free sewing | Required | Harden | Maintain | SewingGraph |
| 1:N sewing | Contract only | Required | Maintain | SewingGraph |
| M:N sewing | Contract only | Required | Maintain | SewingGraph |
| Staged sewing selection | Required | Harden | Maintain | Task panel -> semantic commit |
| Direction/reversal diagnostics | Required | Harden | Maintain | Seam correspondence |
| Curved/length-aware correspondence | Basic | Required | Harden | Seam correspondence service |
| Notches | Basic semantic mark | Required | Grade/export aware | PatternMark |
| Seam allowance | Basic | Required | Production editing/validation | Pattern geometry + metadata |
| Grainline/internal marks | Basic | Required | Production annotations | PatternMark |
| Grading | No | Basic | Full grading review | Pattern metadata / expressions |
| DXF/SVG/TechDraw export | No | Basic | Manufacturing interoperability | Native export adapters |
| Arrangement points | Basic deterministic placement | Required | Rich avatar/body points | Fitting metadata + Placement |
| Wrap/superimpose/reset | Basic | Required | Harden | Fitting workbench |
| Parametric human mannequin | Provider contract | Required | Higher fidelity provider | AvatarService -> DrapeTarget |
| Generic FreeCAD target | Provider contract | Required | Multi-target + subelements | DrapeTarget |
| Material presets | Basic CPU reference | Required | Expanded material library | Simulation properties |
| Particle-distance quality | Basic | Required | Presets + validation | Simulation quality |
| Pinning | Basic | Required | Harden | Simulation constraints |
| Fit/stress/strain/pressure maps | No | Basic diagnostics | Required | Simulation result analysis |
| Plot/nesting/manufacturing validation | No | Export foundation | Required | Pattern/production layer |
| Pleats/folds/topstitch/buttons/linings | No | No | Required | Construction semantics |
| Optional native solver backend | No | No | Benchmark only | Backend adapter |

## Confirmed CLO interaction patterns

Official CLO documentation currently exposes Segment Sewing, Free Sewing, 1:N sewing and M:N sewing. M:N workflows are explicitly staged: select the first side, commit it, select the second side, commit it. Delete cancels the last staged action, Esc cancels the operation, and inappropriate selections are rejected visibly. Directional notches communicate correspondence and reversal. This is the model to emulate in FreeCAD's Sewing task panel rather than creating seams immediately on every click.

CLO also treats seam allowance, notches, grading, DXF interchange and plotting as explicit production workflows. Seam allowance can have persistent editing/lock/start/end/intersection behavior; notches have persistent placement/display behavior and grading; DXF workflows include notch handling and curve optimization; plotting provides print-layout and annotation controls.

CLO's modular/block workflow is another useful production reference: patterns and block boxes can be sewn using the normal sewing tools, but some modular operations intentionally restrict the allowed sewing relationship. This supports representing construction kinds and allowed relationship types explicitly instead of assuming every seam is interchangeable.

## UI/UX rules for FreeCAD

### Task-panel hierarchy

Every Cloth task panel should read in this order:

1. **Context** — selected garment/piece/target and validity state.
2. **Primary action** — the next action that advances the workflow.
3. **Secondary actions** — inspection and reversible edits.
4. **Parameters** — persistent values, grouped and unit-aware.
5. **Recovery** — Refresh, Repair, Reset, with an explicit reason when state is stale.

### Sewing interaction

- Highlight all sewable candidates when a sewing tool is active.
- Show the first staged side distinctly from the second.
- Show direction markers and length/correspondence diagnostics before commit.
- Make invalid candidates visibly invalid and prevent commit.
- `Enter` completes a stage; `Delete` undoes the last stage; `Esc` cancels the operation.
- Persistent seams are created/changed only on explicit commit.
- Selection should be usable from both 2D pattern geometry and 3D garment geometry where practical.

### Fitting interaction

- Treat arrangement as deterministic construction state, not solver state.
- Provide Preview -> Apply for placement changes when several values are edited together.
- Provide Reset 2D Arrangement and Reset 3D Arrangement as normal recovery commands.
- Keep Superimpose as a deterministic placement operation.
- Make collision target identity explicit: `Mannequin` and `FreeCAD Geometry` are providers of the same DrapeTarget contract.

### Simulation interaction

- `Run` is primary; `Step` is secondary/debug; `Reset` is recovery/destructive.
- Display current simulation validity and stale reasons before allowing Run/Step.
- Separate material and quality controls from collision-target selection.
- Make preview/final quality choices explain the performance/mesh trade-off.

## Prototype -> MVP -> production decision rule

A feature is **prototype** when it proves a boundary or interaction contract. It is **MVP** when the absence of it prevents a repeatable garment workflow. It is **production** when it adds manufacturing, diagnostics, fidelity or advanced construction without changing authoritative Pattern/Sewing/DrapeTarget contracts.

Do not pull production features forward merely because they are visible in CLO. Stabilize the public FreeCAD workflow and invalidation model first.

## Avatar direction

Two providers are required, not two simulation paths:

```text
                    DrapeTarget
                   /           \
        Human Mannequin      FreeCAD Geometry
        AvatarService         Shape/Body/Mesh
              \                 /
               -> CollisionSurface -> Simulation
```

The human provider should be recognizably humanoid and persist measurements, pose and rebuild state. The generic provider should accept normal FreeCAD shape-bearing objects without manual conversion. Both must respect Placement/recompute and invalidate target-dependent state deterministically.

A high-fidelity imported/generated body is a later provider behind the same boundary. It must not become a prerequisite for normal garment workflows.

## Sources

- CLO Help Center, 3D Sewing: https://support.clo3d.com/hc/en-us/articles/360007863993-3D-Sewing
- CLO Help Center, M:N Free Sewing: https://support.clo3d.com/hc/en-us/articles/360001754668--3D-Tool-M-N-Free-Sewing
- CLO Help Center, M:N Segment Sewing: https://support.clo3d.com/hc/en-us/articles/115000497727--2D-Tool-M-N-Segment-Sewing
- CLO Help Center, Segment Sewing: https://support.clo3d.com/hc/en-us/articles/115000498767--2D-Tool-Segment-Sewing
- CLO Help Center, Free Sewing: https://support.clo3d.com/hc/en-us/articles/360001754628--3D-Tool-Free-Sewing
- CLO Help Center, Seam Allowance: https://support.clo3d.com/hc/en-us/articles/360001?placeholder
- CLO Help Center, Notch: https://support.clo3d.com/hc/en-us/articles/115015735467-Notch
- CLO Help Center, Set Grading: https://support.clo3d.com/hc/en-us/articles/115015798567-Set-Grading
- CLO Help Center, DXF import/export: https://support.clo3d.com/hc/en-us/articles/115000493067-2D-Pattern-DXF-Import-Export
- CLO Help Center, Plot Patterns: https://support.clo3d.com/hc/en-us/articles/360001557927-Plot-Patterns
- CLO Help Center, Sew Blocks: https://support.clo3d.com/hc/en-us/articles/360001216867-Sew-Blocks
