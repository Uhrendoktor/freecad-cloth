# FreeCAD Cloth

<p align="center">
  <a href="https://github.com/Uhrendoktor/freecad-cloth/actions/workflows/canonical-execution.yml">
    <img src="https://github.com/Uhrendoktor/freecad-cloth/actions/workflows/canonical-execution.yml/badge.svg?branch=main" alt="Canonical execution">
  </a>
  <img src="https://img.shields.io/badge/FreeCAD-1.1%2B-4a4a4a?logo=freecad" alt="FreeCAD 1.1+">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776ab?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/License-LGPL--2.1%2B-2f2f2f" alt="LGPL 2.1 or later">
</p>

<p align="center">
  <strong>Native 2D pattern authoring → semantic sewing → direct 3D fitting → mannequin posing → cloth draping → visual diagnosis</strong>
</p>

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Finished sewn tunic draped over the native FreeCAD mannequin" width="900">
</p>

FreeCAD Cloth is an open-source set of native FreeCAD workbenches for parametric sewing-pattern design, garment assembly, 3D fitting, mannequin posing, cloth simulation and visual inspection.

The project is designed around a single saved FreeCAD document as the persistence authority. Native Sketcher owns editable 2D geometry; Cloth owns garment semantics; DrapeTarget owns target selection and collision authority; the physics backend consumes derived simulation inputs.

---

## What the project looks like

The README is organized as a visual walkthrough rather than a feature dump. The images below show the same garment workflow from source geometry through final drape.

| Stage | Workbench / mode | What you see |
| --- | --- | --- |
| **01 · Pattern** | **Cloth Pattern** | Native Sketcher geometry, piece metadata, seam allowance, grainline and construction marks |
| **02 · Sewing** | **Cloth Sewing** | Semantic seams, direction/correspondence, validation state and 2D/3D relationship |
| **03 · Arrange** | **Interactive Arrange** | Pattern pieces positioned directly in the 3D fitting scene with arrangement-point snapping |
| **04 · Pose** | **Pose Mode** | Selectable mannequin joints, direct rotation gizmo, symmetry, snapping and presets |
| **05 · Simulate** | **Cloth Simulation** | Quality/material controls, target validity, step/run/reset and persisted simulation state |
| **06 · Diagnose** | **Cloth Diagnostics** | Stress visualization, mesh/drape checks, six-side inspection and recoverable invalid states |

### The complete visual workflow

~~~mermaid
flowchart LR
    P["Cloth Pattern<br/>Native Sketcher"]
    S["Cloth Sewing<br/>Semantic seams"]
    A["Arrange / Fit<br/>Direct manipulation"]
    T["DrapeTarget<br/>Mannequin or any FreeCAD target"]
    M["Cloth Simulation<br/>Mesh + PBD"]
    I["Inspect / Diagnose<br/>360° + diagnostics"]
    R["Iterate<br/>Edit → Recompute → Rebuild"]

    P --> S --> A --> T --> M --> I
    I --> R
    R --> P
    R --> S
    R --> A
    R --> T
~~~

---

## 01 · Pattern source: native 2D garment geometry

The pattern editor is intentionally FreeCAD-native. A PatternPiece keeps a stable semantic identity and points back to authoritative Sketcher geometry rather than maintaining a second dimensional solver.

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Cloth Pattern workbench showing editable native Sketcher garment geometry" width="900">
</p>

**Visual review points**

| Inspect | Expected visual information |
| --- | --- |
| Piece boundaries | Clean closed outlines with the intended garment silhouette |
| Construction data | Seam allowance, grainline, notches and internal marks remain distinguishable from the authoritative boundary |
| Editing authority | The visible geometry is native Sketcher geometry, not a duplicate polygon editor |
| Document state | Pattern pieces remain recomputable and persist through save/reload |

---

## 02 · Sewing: semantic garment assembly

Sewing operates on semantic pattern edges rather than generated mesh edge order. The visual goal is that seam identity, direction and validation state can be understood before the garment is simulated.

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png" alt="Cloth Sewing workbench showing semantic seam setup and validation" width="900">
</p>

**Visual review points**

| Inspect | Expected visual information |
| --- | --- |
| Seam identity | The intended source edge on each pattern piece is unambiguous |
| Direction | Reversal / correspondence choices are visible before commit |
| Validation | Invalid or stale references are explicit instead of silently retargeted |
| 2D ↔ 3D relationship | A seam can be focused in the assembled scene while the native Sketcher edge remains authoritative |

---

## 03 · Arrange / Fit: direct 3D manipulation

The fitting workflow is viewport-first. Pattern pieces can be dragged directly in the FreeCAD 3D scene, snapped to persistent arrangement points, reset to their saved home arrangement and fitted to the current target.

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.png" alt="Current Interactive Arrange task panel with a snap target preview" width="900">
</p>

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png" alt="Current sewn garment arranged around the mannequin before simulation" width="900">
</p>

### Interaction model

| Action | Visual behavior |
| --- | --- |
| **Select a piece** | The intended PatternPiece becomes the active fitting object |
| **Drag in 3D** | Placement follows the viewport instead of requiring numeric coordinates |
| **Approach an arrangement point** | A transient snap target appears at the destination |
| **Release** | The placement is committed as one undoable FreeCAD transaction |
| **Reset arrangement** | All pieces return to the persisted pre-arrangement positions |
| **Fit view** | The target and garment are brought back into a useful framing |
| **Snap off** | Free dragging remains available when point snapping is not desired |

The arrangement scene persists placement, arrangement points, symmetry state and the selected DrapeTarget. Arrangement is deliberately independent from solver state.

---

## 04 · Pose Mode: direct mannequin posing

The mannequin editor separates posing from anthropometric setup. The viewport is the primary manipulation surface; the task panel provides selection, symmetry, angle snapping, presets, precision editing and explicit commit/cancel actions.

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/avatar-pose-mode.png" alt="Current Cloth Pose Mode task panel with mannequin joints and rotation gizmo" width="900">
</p>

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-front.png" alt="Current front view of the Cloth human mannequin used as a drape target" width="420">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-rear.png" alt="Current rear view of the Cloth human mannequin used as a drape target" width="420">
</p>

### Pose interaction model

| Control | What it communicates |
| --- | --- |
| **Joint selection** | Joints can be selected from the anatomical tree or directly in the 3D view |
| **Rotation gizmo** | Colored rings expose axis-specific rotation; the trackball provides free rotation |
| **Symmetry** | Left/right edits can be mirrored around the mannequin center line |
| **Snap 5°** | Dragged rotations can be quantized to 5° increments |
| **Presets** | Standing, Sewing and Sitting establish a clear starting pose |
| **Precision** | Exact X/Y/Z Euler values remain available behind progressive disclosure |
| **Apply & Rebuild** | Staged pose values become persistent mannequin state and rebuild derived geometry |
| **Cancel** | Staged edits are discarded without replacing the saved pose |

The pose is document-driven: joint rotations are persistent, while the deformed mesh is derived and rebuildable. Parent joints propagate to their descendants.

### Avatar reference

![Cloth Avatar 360° turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-avatar-turntable.gif)

---

## 05 · Simulation: from arranged garment to physical drape

The simulation workbench keeps normal garment controls visible while expert settings remain progressively disclosed. The target is explicit, the simulation state is persistent, and Run / Step / Reset provide deterministic recovery paths.

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif" alt="360 degree view of the arranged sewn garment" width="820">
</p>

### The target boundary

DrapeTarget is the common collision boundary for:

- the native human mannequin;
- an ordinary FreeCAD Shape / PartDesign / Body / Mesh;
- future replaceable target providers.

Changing the target, pose or authoritative collision geometry invalidates target-dependent derived state instead of silently consuming stale data.

### Simulation controls shown in the public workflow

| Visible control / state | Why it matters |
| --- | --- |
| **Target identity / validity** | Confirms what the cloth is actually colliding with |
| **Quality preset** | Keeps common simulation choices understandable without exposing every solver detail |
| **Particle distance / density** | Makes resolution changes explicit |
| **Fabric parameters** | Keeps physical material inputs separate from target selection |
| **Pin mode / pin selection** | Makes constraints visible and persistent |
| **Run / Step / Reset** | Supports both normal use and controlled inspection/recovery |
| **Stale / invalid state** | Shows the reason derived state must be rebuilt |

---

## 06 · Final drape: inspect the garment, not just the solver log

The main visual acceptance target is the finished garment after real simulation steps.

![Sewn tunic draping over mannequin](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-tunic-mannequin-motion.gif)

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif" alt="360 degree drape of the sewn tunic over the mannequin" width="900">
</p>

For a still comparison, the generated visual fixture also captures the final draped state:

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Final draped garment over the mannequin" width="900">
</p>

### What to inspect in the final silhouette

| Region | Visual questions |
| --- | --- |
| **Shoulders** | Does the cloth meet the shoulder target without obvious penetration or detachment? |
| **Neckline** | Does the sewn opening remain coherent as the avatar pose and cloth settle? |
| **Side seams** | Do the panels remain assembled and spatially continuous? |
| **Torso** | Do folds follow the body instead of reading like a rigid sheet? |
| **Hem** | Does the lower edge remain connected and plausible rather than exploding or collapsing? |
| **Back** | Does the rear panel remain consistent with the front-panel assembly? |
| **Global silhouette** | Does the garment read as one continuous garment from every side? |

---

## 07 · Six-side review: front, rear, left, right, top and bottom

A single hero render can hide collisions, detached panels or unexpected deformations. The README therefore exposes the same six-side review used by the canonical visual fixture.

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png" alt="Draped garment front view" width="280">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-rear.png" alt="Draped garment rear view" width="280">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-left.png" alt="Draped garment left view" width="280">
</p>

<p align="center">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-right.png" alt="Draped garment right view" width="280">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-top.png" alt="Draped garment top view" width="280">
  <img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-bottom.png" alt="Draped garment bottom view" width="280">
</p>

<details>
<summary><strong>Human visual checklist</strong></summary>

The visual review should confirm:

- no visible cloth penetration through the cube or mannequin;
- no exploding, collapsed, detached or self-inverted cloth;
- authored pins and seams behave as expected;
- motion progresses without sudden topology changes;
- the settled silhouette and folds read as fabric rather than a rigid sheet;
- front and rear pattern panels remain coherent;
- the garment remains plausible when the camera leaves the hero angle.

</details>

---

## 08 · Diagnostics: make failure visible

Diagnostics are meant to explain a valid result and to refuse stale or invalid state rather than presenting misleading visualizations.

![Stress diagnostic map](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-diagnostics.png)

Typical visual evidence includes:

| Evidence | Purpose |
| --- | --- |
| **Stress map** | Highlights where the current garment state is mechanically loaded |
| **Six-side views** | Exposes problems hidden by a single camera angle |
| **Animation** | Shows whether instability appears during motion or only after settling |
| **Drape metrics** | Distinguishes a visually plausible result from a numerically invalid one |
| **Stale-state guard** | Prevents a diagnostic map from being generated from an invalid simulation state |

---

## 09 · Simulation ladder: controlled visual complexity

The collision ladder increases complexity one rung at a time. It stops at the first failing rung instead of allowing later stages to obscure the cause.

| Rung | Scenario | What the viewer is checking |
| ---: | --- | --- |
| **1** | One panel on cube, pinned | Basic motion and rigid contact |
| **2** | One panel on cube, unpinned | Unconstrained rigid contact |
| **3** | Two panels on cube, no seam | Multi-piece collision |
| **4** | Two panels on cube, small seam | Initial sewing + collision interaction |
| **5** | Two panels on cube, large seam | Stress seam/contact coupling |
| **6** | One panel on mannequin, pinned | Basic body collision |
| **7** | One panel on mannequin, unpinned | Unconstrained body contact |
| **8** | Two panels on mannequin, no seam | Multi-piece body collision |
| **9** | Two panels on mannequin, small seam | Garment assembly on body |
| **10** | Two panels on mannequin, large seam | Final seam/contact coupling |

Each rung captures steps 0, 1, 5, 15, 45 and 90. Human review stops at the first visually or numerically failing rung.

![Blanket collision and drape](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif)

The blanket-over-cube case is intentionally simple: it verifies that the runtime can move cloth, collide with a rigid target and produce a stable visual sequence before the mannequin garment case is attempted.

---

## 10 · Visual capability map

The following is the intended reading order of the current public workflow.

| Capability | Visual proof in this README | Current boundary |
| --- | --- | --- |
| Native Sketcher pattern authoring | Pattern screenshot | FreeCAD Sketcher remains the editable geometry authority |
| Semantic sewing | Sewing screenshot | Seam identity is explicit and validation is fail-closed |
| Direct garment arrangement | Arranged garment + interaction description | Viewport manipulation uses persistent fitting-scene state |
| Arrangement snapping | Snap interaction description | Persistent arrangement points drive the placement target |
| Mannequin posing | Avatar gallery + Pose Mode interaction map | Current direct pose editor targets the MakeHuman HM08 provider |
| Target-neutral fitting | Target boundary section | Mannequin and generic FreeCAD geometry share the DrapeTarget boundary |
| Cloth simulation | Arranged and draped turntables | PositionBasedDynamics is the production physics runtime |
| Six-side review | Six generated stills | Front/rear/left/right/top/bottom are reviewed as one audit |
| Stress inspection | Diagnostic map | Diagnostics consume valid simulation state only |
| Repeatable validation | Simulation ladder | Visual and numerical failure stop the ladder at first failure |

---

## 11 · Architecture at a glance

The document model is intentionally split into authoritative inputs, semantic state and rebuildable derived state.

~~~mermaid
flowchart TB
    subgraph Authoring["Authoritative authoring"]
        SK["Native Sketcher geometry"]
        PP["PatternPiece"]
        SM["Pattern metadata<br/>allowance · grainline · notches · marks"]
        SK --> PP
        PP --> SM
    end

    subgraph Semantics["Garment semantics"]
        SG["SewingGraph / semantic seams"]
        FS["FittingScene<br/>placements · arrangement points · measurements"]
        AV["Avatar / Pose"]
        SG --> FS
        AV --> FS
    end

    subgraph Target["Target authority"]
        DT["DrapeTarget"]
        CS["Collision surface"]
        DT --> CS
    end

    subgraph Derived["Derived simulation state"]
        MM["Simulation mesh"]
        PH["PositionBasedDynamics state"]
        DG["Visual diagnostics"]
        MM --> PH --> DG
    end

    PP --> SG
    FS --> DT
    PP --> MM
    SG --> PH
    CS --> PH
~~~

### Authority rules

| Concern | Authority | Derived / transient |
| --- | --- | --- |
| 2D dimensions and constraints | Native Sketcher | Pattern mesh / solver input |
| Pattern semantics | PatternPiece + semantic metadata | Rendered / simulated geometry |
| Seam identity | Semantic edge references | Generated stitch samples |
| Fitting placement | Persisted PiecePlacements | Mouse drag preview |
| Arrangement targets | Persisted arrangement points | Snap marker |
| Avatar pose | Persisted pose values | Deformed avatar mesh |
| Collision | DrapeTarget / collision surface | Solver broad/narrow-phase data |
| Simulation | Saved simulation inputs + runtime state | Temporary viewport effects |
| Diagnostics | Valid current simulation state | Stale diagnostic maps |

The saved FreeCAD document is the persistence authority. GUI selection, gizmos, snap markers and other viewport previews are transient.

---

## 12 · UI design language

The public UI is deliberately organized around the same interaction pattern across workbenches:

**Context → Primary action → Secondary actions → Parameters → Recovery**

### Direct manipulation

Use the viewport when the operation is spatial:

**Pattern arrangement**

Select → Drag → Snap preview → Release → Persistent placement

**Mannequin posing**

Select joint → Rotate gizmo → Stage pose → Apply & Rebuild

### Progressive disclosure

The normal path keeps the task panel readable. Expert simulation/material/precision controls are available without making the common interaction depend on numeric inputs.

### Recovery is visible

Reset, Cancel, Refresh/Rebuild, Fit view and stale-state messages are part of the workflow rather than hidden implementation details.

---

## 13 · Current implementation boundary

The project deliberately does not present every commercial garment-CAD feature as complete.

| Area | Current public workflow | Not claimed as complete |
| --- | --- | --- |
| Pattern | Native Sketcher-backed pieces and metadata | Full grading / production marker workflows |
| Sewing | Semantic seams, direction/correspondence and validation | Full industrial sewing-assistance suite |
| Fitting | Direct arrangement, persistent points and reset/recovery | Full automatic fitting / tape / extraction toolset |
| Avatar | Native mannequin, pose controls and target-neutral boundary | Full production human-avatar provider ecosystem |
| Simulation | Quality/material controls, target validation, step/run/reset | Photorealistic rendering or cloud simulation |
| Diagnostics | Drape/stress visual inspection | Full commercial fit/pressure/strain analysis suite |
| Production | SVG/DXF-oriented pattern output path | End-to-end manufacturing planning and nesting |
| Construction | Semantic foundations | Complete trims/closures/construction-detail library |

The roadmap keeps these boundaries explicit so that README visuals do not imply capabilities that are only planned.

---

## 14 · Runtime and installation

The supported development, packaging, test and canonical FreeCAD CI baseline is **Python 3.12+**.

The PositionBasedDynamics runtime is the production physics solver. Its installation is an optional simulation extra, but the supported FreeCAD development/CI baseline uses a FreeCAD build with an embedded Python 3.12 runtime.

Start with [Installation](docs/INSTALLATION.md), then run the [Blanket over Cube](docs/EXAMPLES.md) example before the full tunic path.

---

## 15 · Validation and reproducibility

There is one canonical GitHub Actions workflow:

.github/workflows/canonical-execution.yml

It covers:

- Python/static/property checks;
- real FreeCAD/Xvfb GUI acceptance;
- direct fitting and Pose Mode UI contracts;
- native Sketcher → Sewing → Simulation coverage;
- the blanket visual fixture;
- the simulation ladder and real motion frames;
- six-side turntable generation;
- diagnostic evidence and stale-state guards.

The README images are generated evidence from those validation paths. The generated screenshot/animation source is maintained separately from this human-facing README so that visual evidence can be regenerated without turning documentation into a second test harness.

---

## Documentation

Start at [docs/README.md](docs/README.md). Useful next stops are:

- [Installation](docs/INSTALLATION.md) — setup and supported runtime;
- [Workbench Guide](docs/WORKBENCH_GUIDE.md) — end-to-end user workflow;
- [Architecture](docs/ARCHITECTURE.md) — domain ownership and dependency direction;
- [Research](docs/RESEARCH.md) — garment-UX and visual interaction research;
- [Roadmap](docs/ROADMAP.md) — remaining P1 / production work;
- [Release Gates](docs/RELEASE_GATES.md) — executable definition of “complete”.

Agent-specific execution policy remains in [AGENTS.md](AGENTS.md), while AGENT_STATUS.md and TOOL_STATE.md hold live coordination state and are not intended as human project marketing material.

## License

This project is licensed under the GNU Lesser General Public License v2.1 or later; see [LICENSE](LICENSE).
