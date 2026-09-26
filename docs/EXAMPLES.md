# Examples

The project uses a complexity ladder so a new user can validate the installation before opening a full garment.

| Example | Complexity | What it demonstrates | Visual validation |
|---|---|---|---|
| Blanket over Cube | Basic | one native Sketcher pattern, one FreeCAD collision target, explicit pins, gravity and drape | five checkpoints + motion GIF |
| Tunic | Advanced | multiple native pattern pieces, semantic seams, mannequin collision, material/quality controls, diagnostics and production export | six views + diagnostic map + arranged/draped turntables + motion GIF |

## 1. Blanket over Cube

Use this as the first installation smoke test.

### Human path

1. Open **Cloth Pattern** and create a simple rectangular pattern piece using native Sketcher-backed pattern authoring.
2. Place the resulting cloth above a simple FreeCAD cube/shape.
3. In **Cloth Simulation**, use **Create Drape Target** with the selected FreeCAD shape/mesh.
4. Create/open the simulation and pin two blanket corners.
5. Open **Simulation Controls** and press **Run 30**.
6. Verify that the blanket visibly moves toward and around the cube.

The example intentionally avoids the human avatar so a new installation can isolate pattern, collision, pinning, and solver problems.

### Executable evidence

The canonical fixture is `tests/freecad_visual_examples.py`. During CI it writes:

- five checkpoint PNGs;
- sixteen motion PNGs;
- a validated `blanket-motion.gif`;
- `blanket-visual.log` containing mesh, movement, and material-presentation assertions.

The workflow expects `blanket-visual-acceptance=passed`, `mesh=passed`, and `movement=passed` before publishing the evidence artifact.

## 2. Tunic

The tunic is the advanced garment acceptance scenario.

### Human path

1. Author or open the multi-piece native Sketcher patterns.
2. In **Cloth Sewing**, create and validate the semantic seam relationships.
3. In **Cloth Simulation**, create/select the mannequin target with **Create Mannequin Drape Target**.
4. Arrange the garment pieces using the persistent fitting/placement state before simulation.
5. Open **Simulation Controls**, select an appropriate quality preset, verify target status, and use **Run 30** or **Step**.
6. Inspect seams in 2D/3D and inspect the simulation result/diagnostics before saving or exporting.
7. Save/reload when persistence is part of the task.

Do not copy test-only fixture coordinates or pin indices from the CI scripts into a general user workflow. The scripts are evidence of the public contract, not a second user interface.

### Executable evidence

The broader garment path is exercised by `tests/freecad_garment_e2e_smoke.py` and the associated visual audit/turntable jobs in [.github/workflows/canonical-execution.yml](../.github/workflows/canonical-execution.yml).

The canonical workflow checks, among other states:

- seam correspondence and 2D/3D seam markers;
- fitting/arrangement persistence;
- garment hierarchy persistence;
- material presentation persistence;
- mannequin `DrapeTarget` validity;
- simulation reset/run state;
- save/reload and invalidation behavior.

Generated visual evidence is written under `docs/images/generated/`. Stable README-facing assets are copied to the `docs/screenshots` branch.

## Visual regression policy

Every public example should have an executable visual fixture. README images are derived from those fixtures rather than manually captured screenshots.

The canonical validation ladder is:

1. a simple example;
2. the production tunic;
3. a moving simulation sequence;
4. a fixed final turntable;
5. diagnostic/material state where the example supports it.

A screenshot is evidence only when the corresponding executable assertion and artifact are present. Camera-only rotation does not count as simulation-motion evidence.
