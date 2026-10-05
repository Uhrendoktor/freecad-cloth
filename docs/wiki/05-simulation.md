# 05 · Cloth simulation

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged-turntable.gif" alt="Arranged sewn garment turntable" width="820"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-tunic-mannequin-motion.gif" alt="Sewn tunic motion and draping sequence" width="900"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-turntable.gif" alt="Final draped garment turntable" width="900"></p>

## What the feature is

The simulation stage turns authored garment semantics plus fitting state plus a collision target into derived cloth state.

The production runtime is PositionBasedDynamics behind a small <code>ClothBackend</code> adapter boundary.

## What a human should see

| Control/state | Why it must be visible |
| --- | --- |
| Target identity | The user can tell what the cloth is colliding against |
| Target validity | Stale or invalid target state is shown before Run/Step |
| Quality | Common simulation choices are understandable without solver jargon |
| Material | Fabric density and physical parameters are separate from target selection |
| Pin mode / pin selection | Constraints are explicit and persistent |
| Run / Step / Reset | The user can advance, inspect or recover deterministically |
| Stale reason | Invalid derived state has an actionable explanation |

## Material and resolution

Simulation inputs include quality/resolution and material state. Presentation properties such as cloth color, roughness, specular response and transparency are persisted with the simulation/material state.

Changing persistent simulation inputs invalidates derived runtime state instead of silently reusing old particles or constraints.

## Pins and sewing

Pinning is explicit.

The current pinning model distinguishes:

- <strong>Automatic</strong> — preserve legacy automatic behavior where appropriate;
- <strong>Explicit</strong> — use the persisted PinSelection;
- <strong>None</strong> — run with zero solver pins.

Sewing constraints are derived from the semantic sewing model; they are not hand-created mesh-index relationships.

## Target boundary

<code>DrapeTarget</code> is the common collision authority for:

- the native mannequin;
- ordinary FreeCAD geometry;
- future interchangeable providers.

A target change, pose change or collision-geometry change must invalidate target-dependent derived state.

## Human simulation review

The visual proof should show a clear progression:

<strong>Arranged garment → motion → contact → fold development → settled garment</strong>

A camera rotation alone does not count as simulation motion.

A valid final result should be checked for:

- collision penetration;
- exploding/collapsed geometry;
- detached seams;
- sudden topology changes;
- rigid-sheet behavior;
- implausible final silhouette.

## Simple-first simulation ladder

Canonical evidence begins with simple collision scenes before the sewn mannequin garment path.

The ladder moves from a single panel on a cube through two-panel cube cases and then through single/two-panel mannequin cases. This catches basic collision instability before garment complexity can hide the cause.

## Automated evidence

Relevant fixtures:

- <code>tests/freecad_pbd_cube_ladder.py</code>
- <code>tests/freecad_pbd_avatar_ladder.py</code>
- <code>tests/freecad_pbd_contact_diagnostics.py</code>
- <code>tests/freecad_realtime_benchmark.py</code>
- <code>tests/freecad_screenshot_source.py</code>
- <code>tests/freecad_garment_e2e_smoke.py</code>

Source:

- <code>freecad_cloth/simulation/</code>
- <code>freecad_cloth/common/PatternSimulationAdapter.py</code>
- <code>freecad_cloth/common/DrapeVisualSanity.py</code>
- <code>freecad_cloth/common/MeshValidation.py</code>

The generated turntables and motion frames are the primary human-review artifacts; logs are supporting evidence.
