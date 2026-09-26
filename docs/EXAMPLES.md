# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Evidence |
|---|---|---|---|
| Blanket over Cube | Basic | native Sketcher pattern, persistent FreeCAD-geometry `DrapeTarget`, explicit `PinSelection`, gravity, drape and motion | `tests/freecad_visual_examples.py` + published blanket motion GIF |
| Tunic | Advanced | native Sketcher pieces, semantic seams, mannequin/`DrapeTarget`, persistent arrangement, quality/material controls, diagnostics and real simulation | `tests/freecad_tunic_audit.py` / production visual artifacts |

## 1. Blanket over Cube

### What the canonical fixture contains

The authoritative blanket fixture uses:

- a **200 × 200 mm** native Sketcher rectangle;
- a **180 × 180 × 60 mm** FreeCAD cube;
- the cube as the persistent **FreeCAD Geometry** `DrapeTarget`;
- the two opposite top-edge corners stored in `PinSelection`;
- the scene's persistent `PinMode=Automatic`;
- gravity-driven simulation and real viewport captures.

### Manual goal

1. In **Cloth Pattern**, create or adopt a native Sketcher rectangle as a PatternPiece.
2. In **Cloth Simulation**, select the cube and run **Create Target** (`ClothDrape_CreateTarget`).
3. Use **Edit Drape Target** (`ClothDrape_EditTarget`) to confirm **Provider = FreeCAD Geometry**, the cube as **Source**, and a current collision surface.
4. Create a simulation with **Create Simulation** (`ClothSimulation_Create`) and verify the PatternPiece is present in `ClothPieces`.
5. Open **Simulation Controls** (`ClothSimulation_Edit`), confirm the target is ready, then use **Step Simulation** / **Step** or **Run Simulation** / **Run 30**.
6. Inspect the viewport for actual cloth motion toward and around the cube.

The public GUI exposes **Pinning mode** as **Automatic**, **Explicit**, or **None**. Automatic preserves legacy behavior, Explicit uses only `PinSelection`, and None creates zero solver pins. The current panel is not a mesh-vertex selection editor; the two-corner pinning in the canonical blanket fixture is therefore executable evidence, not a hidden manual UI operation.

### Blanket artifact behavior

The visual fixture writes its intermediate evidence under `docs/images/generated/blanket-example` (or the `CLOTH_SCREENSHOT_DIR` override):

- `checkpoint-000.png` for the initial state;
- checkpoints at steps **15, 30, 60, and 120**;
- `motion-000.png` for the pre-movement state;
- **16** motion PNGs spanning the simulation to step 120.

The publication workflow converts the validated motion sequence into the README's stable `cloth-blanket-motion.gif` asset. These generated files are evidence; the saved FreeCAD document and source fixtures remain authoritative.

The canonical checks also validate finite/connected cloth, meaningful movement between early and late states, and real FreeCAD viewport captures rather than placeholder images.

## 2. Tunic

The tunic is the validated advanced/P0 acceptance scenario, but it is not a claim of full commercial garment-suite parity.

### Pattern

1. Create two native Sketcher pattern pieces.
2. Keep Sketcher as the geometry authority; use **Edit native Sketch…** for geometry changes.
3. When starting from an existing Sketcher object, use **Create Pattern Piece From Selected Sketch** (`ClothPattern_CreateFromSketch`).
4. For a production document root, use **Create Garment** (`ClothPattern_CreateGarment`).

### Sewing

1. Select compatible semantic edges from the two PatternPieces.
2. Run **Create Seam** (`ClothSewing_CreateSeam`).
3. Use the staged **Preview**, inspect validation, then **Commit** or **Cancel**.
4. Use **Create Sewing Operation** and **Validate Sewing** for persistent correspondence and diagnostics.
5. Use **Focus Seam in 3D** and **Edit Seam Side A/B in Sketcher** when inspecting a seam.

Seams use deterministic colors in the 2D sewing view and retain their placed/world-space 3D presentation. A changed Sketcher semantic edge invalidates the seam until it is explicitly repaired or recreated.

### Arrange / Fit

Use the **Cloth Sewing** fitting/avatar commands for persistent placement:

- **Create Avatar** (`ClothFitting_CreateAvatar`);
- **Create Fitting Scene** (`ClothFitting_CreateScene`);
- **Add Selected Pattern Pieces** (`ClothFitting_AddPieces`);
- **Create Arrangement Point** / **Set Arrangement Point**;
- **Apply Selected Arrangement** (`ClothFitting_ApplyArrangementPoint`);
- **Reset Arrangement** (`ClothFitting_ResetArrangement`).

The current human-facing workflow describes explicit arrangement and persistent placements. It does not claim a general automatic body-target snapping operation without separate acceptance evidence.

### Drape Target and simulation

1. Create a mannequin target with **Create Mannequin Target** (`ClothDrape_CreateMannequinTarget`) or a generic geometry target with **Create Target** (`ClothDrape_CreateTarget`).
2. Use **Edit Drape Target** and **Refresh Drape Target** when the source or collision settings change.
3. Create/select **Cloth Simulation** and open **Simulation Controls**.
4. Confirm the target status is **ready** before running.
5. Use **Step** for controlled debugging, **Run 30** for the normal batch action, and **Reset** for recovery.

The validated tunic fixture uses `PinMode=None` with zero solver pins and target-relative starting placement. This is a fixture-specific acceptance contract, not a rule that every garment is automatically fitted to its target.

### Current release boundary

The exact current-main release record marks the P0 end-to-end workflow as complete and the tunic visual/simulation audit as passed. The documented scope is still narrower than commercial parity; roadmap features must earn their own executable/visual acceptance evidence before being described as complete.

## Recovery patterns

**Pattern edit breaks a seam:** recompute → **Validate Sewing** → **Repair Seam** only if the original semantic edge still exists; otherwise recreate the seam.

**Target changes produce stale state:** edit the source → **Edit Drape Target** → **Refresh Drape Target** → re-run simulation.

**Garment pieces are missing:** verify the simulation object's `ClothPieces` links and recompute.

**Simulation is blocked:** read the target-state message first; stale collision state is fail-closed.

## Visual regression policy

Every public example has an executable visual fixture. README images are derived from validated fixtures and published to the stable `docs/screenshots` branch. Do not add hand-captured media to document behavior that is not covered by an executable fixture.

