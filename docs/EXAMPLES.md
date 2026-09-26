# Examples

Examples are ordered from the smallest deterministic smoke test to the full garment path.

| Example | Complexity | Best for | Validated evidence |
|---|---|---|---|
| Blanket over Cube | Basic | installation, cloth/collision/pinning sanity | five checkpoints + 16 motion frames + motion GIF |
| Tunic | Advanced | sewing, fitting, mannequin target, material/quality controls, diagnostics, persistence, 2D output | multi-view audit + turntables + motion evidence |

## 1. Blanket over Cube

The blanket example deliberately avoids the human avatar. It proves that a fresh installation can:

- retain a native Sketcher source for a PatternPiece;
- use ordinary FreeCAD geometry through the persistent `DrapeTarget` contract;
- produce a finite, connected simulation mesh;
- apply pins and gravity;
- materially move the cloth during simulation;
- preserve persisted fabric presentation in the viewport.

### Manual GUI path

1. In **Cloth Pattern**, create one PatternPiece from a native Sketcher rectangle.
2. Create a FreeCAD cube/box as the collision geometry.
3. In **Cloth Simulation**, create a simulation scene.
4. Assign the blanket PatternPiece under **Cloth pieces**.
5. Select the cube and use **Create Target** / `ClothDrape_CreateTarget` to create the persistent FreeCAD Geometry DrapeTarget.
6. Pin two opposite boundary particles and run the simulation. The task panel accepts comma-separated particle indices under **Pinned vertices**.
7. Check that the target reports **Drape target collision surface is current**, the state remains finite, and the cloth moves around/against the cube.

The repository's canonical automated example derives the two opposite-corner particle indices from the generated boundary instead of using hard-coded IDs:

- Source: `tests/freecad_visual_examples.py`
- Stable motion media: [blanket motion GIF](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif)

The generated screenshots and GIF are acceptance evidence; they are not intended to be manually replaced.

## 2. Tunic

The tunic is the advanced garment acceptance path. It exercises two native Sketcher pattern pieces, semantic seams, mannequin collision, fitting/arrangement, persisted quality/material state, diagnostics, save/reload, invalidation, and deterministic SVG/DXF export.

### Recommended human workflow

1. **Pattern:** create the front and back PatternPieces as native Sketcher-backed objects. Keep Sketcher as the geometry authority.
2. **Sewing:** create the intended seam relationships, validate correspondence, and confirm seam status before fitting.
3. **Arrange/Fit:** create a fitting scene, assign the native mannequin, add both pieces, and apply the appropriate arrangement points. Use **Reset Arrangement** whenever you need to return to the authored home placements.
4. **Simulation:** create the simulation from the fitting scene, confirm the mannequin is the persistent DrapeTarget, select both cloth pieces, set material/quality, and run the solver.
5. **Diagnose:** open **Cloth Diagnostics** when you need structured post-simulation evidence.
6. **Output:** select the PatternPiece and use **Export Pattern** for deterministic SVG/DXF output. Recompute and repair stale semantic references before exporting.

The repository's tunic audit is the authoritative acceptance fixture for the current advanced path. The fixture contains additional diagnostic/setup code so its outputs are deterministic; do not copy those test-only patches into a normal user document.

### Stable tunic media

![Tunic draped front](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png)

- [Arranged simulation turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif)
- [Draped simulation turntable](https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif)

## 3. Choosing the right example

Use **Blanket over Cube** when you are debugging installation, Triangle imports, basic mesh quality, collision, pinning, or solver motion.

Use **Tunic** when you are debugging semantic seams, arrangement, mannequin targets, garment persistence, diagnostics, or production export.

Do not use the advanced tunic path as evidence that every planned commercial garment capability is implemented. The capability boundary is maintained in [Release gates](RELEASE_GATES.md) and [Roadmap](../ROADMAP.md).

## Visual-regression policy

Every public example has an executable visual fixture. README/example media is derived from those fixtures rather than manually captured screenshots.

The canonical workflow validates:

1. a simple example;
2. the production tunic;
3. actual simulation motion;
4. fixed final/arranged turntables;
5. the diagnostic/quality state where the fixture supports it.

Generated media is published to the stable `docs/screenshots` branch after the corresponding canonical jobs pass.
