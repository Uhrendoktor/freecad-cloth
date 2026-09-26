# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Evidence |
|---|---|---|---|
| Blanket over Cube | Basic | native Sketcher pattern, FreeCAD collision target, pinning, gravity, drape and motion | tests/freecad_visual_examples.py + published blanket motion GIF |
| Tunic | Advanced | native Sketcher pieces, semantic seams, mannequin/DrapeTarget, arrangement/fitting, quality/material controls, diagnostics and real simulation | tests/freecad_tunic_audit.py + production visual artifacts |

## 1. Blanket over Cube

### What to expect

The canonical fixture uses:

- a **200 × 200 mm** native Sketcher rectangle;
- a **180 × 180 × 60 mm** FreeCAD cube;
- the cube as a persistent **FreeCAD Geometry** DrapeTarget;
- explicit opposite-corner pinning;
- gravity-driven cloth motion.

The expected first success is simple: the workbench loads, the pattern becomes a PatternPiece, a DrapeTarget can be built from the cube, and the cloth moves toward and around the cube without non-finite or grossly invalid mesh geometry.

### Manual sequence

1. Open **Cloth Pattern** and create a PatternPiece from a native Sketcher rectangle.
2. Recompute and leave the Sketcher representation as the geometry authority.
3. Create the cube as ordinary FreeCAD geometry.
4. In **Cloth Simulation**, select the cube and run **Create Target** (ClothDrape_CreateTarget).
5. Open **Edit Drape Target** and verify **Provider = FreeCAD Geometry** and the cube as **Source**. Use **Apply & Refresh**.
6. Create a simulation with **Create Simulation**.
7. Verify the PatternPiece is linked in the simulation object's ClothPieces property.
8. Use **Simulation Controls** and confirm the target is valid before running.
9. Run a small number of steps, then **Run 30** and inspect the viewport.
10. Use **Reset** to return to the initial simulation state without discarding the authored quality/material settings.

### Pinning note

The canonical acceptance fixture explicitly maps the two opposite top-edge corners to PinSelection while retaining the simulation's legacy-compatible Automatic pinning mode. The current quality task panel does not expose a click-to-pin mesh editor, so this example is not documentation for a missing UI feature. Treat the executable fixture as the definitive automated installation proof.

The canonical visual job also checks five checkpoints plus 16 motion frames, mesh finiteness/connectivity, drape sanity, movement and material presentation.

## 2. Tunic

The tunic is the advanced acceptance path and should be attempted only after the blanket is working.

### Pattern

1. Create two native Sketcher pieces for the front and back.
2. Adopt each Sketcher object with **Create Pattern Piece From Selected Sketch**.
3. Give the PatternPieces clear labels and recompute.
4. Use **Edit native Sketch…** whenever geometry must change.

### Sewing

1. Select the matching front/back semantic edges.
2. Run **Create Seam**.
3. **Preview** the seam creation.
4. **Commit** the valid result.
5. Create a **Sewing Operation** and run **Validate Sewing**.
6. Use deterministic seam colors, **Focus Seam in 3D**, and **Edit Seam Side A/B in Sketcher** when inspecting or correcting correspondence.

The production fixture checks that semantic edge identities survive into the solver stitch provenance and that seam gaps remain within its acceptance threshold.

### Arrange / Fit

1. Create the Cloth Human Mannequin.
2. Create a **Fitting Scene** and add the front/back PatternPieces with **Add Selected Pattern Pieces**.
3. Create or edit persistent Arrangement Points with **Create Arrangement Point** / **Set Arrangement Point**.
4. Apply them with **Apply Selected Arrangement** to establish the initial piece placements.
5. Use **Reset Arrangement** to recover the saved pre-arrangement state when placement experiments go wrong.

The current release does not claim a general automatic body-snap feature. Arrangement points and persistent piece placements are the documented fitting mechanism.

### Drape Target and simulation

1. Create the mannequin DrapeTarget.
2. Open **Edit Drape Target** and use **Apply & Refresh**.
3. Create/select the Cloth Simulation object.
4. Verify the PatternPieces are in ClothPieces.
5. Choose a quality preset and fabric settings.
6. Use **Step** for controlled debugging or **Run 30** for normal advancement.
7. Use **Reset** to recover without discarding authored quality/material values.
8. Open **Cloth Diagnostics** after a valid drape when the scenario supports the requested map.

The validated tunic fixture uses Pinning mode = None, zero solver pins, and target-relative start placements with step-0 DrapeTarget clearance checks. This is a fixture-specific acceptance detail; it is not a prescription that every garment is automatically snapped to its target.

## Recovery patterns

**Pattern edit breaks a seam:** recompute → Validate Sewing → Repair Seam if the semantic edge still exists; otherwise recreate the seam.

**Mannequin/target changes produce stale state:** edit the target → verify Provider/Source → Apply & Refresh → rerun simulation.

**Garment pieces are missing from the simulation:** verify ClothPieces links and recompute.

**Tunic starts in the wrong place or intersects the body:** correct persistent arrangement/placements first; then refresh the DrapeTarget. Do not compensate by changing unrelated solver quality blindly.

**Simulation is blocked:** read the target-state message. The solver intentionally refuses stale or invalid collision state.

## Visual regression policy

Every public example has an executable visual fixture. README images are derived from those validated fixtures and published to the stable docs/screenshots branch.

Use only the currently published assets referenced by [README.md](../README.md). Do not add hand-captured screenshots or GIFs to document behavior that is not covered by an executable fixture.

## Current release boundary

The blanket and tunic examples demonstrate the current P0 end-to-end workflow. They do **not** establish full commercial garment-suite parity. Grading/nesting, richer construction features, higher-fidelity avatar providers, advanced diagnostics and other Production roadmap items remain future scope unless separately validated.
