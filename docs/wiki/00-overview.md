# 00 · End-to-end overview

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Final draped garment" width="900"></p>

The intended workflow is a continuous garment-authoring loop:

<strong>Pattern → Sewing → Fitting → Pose → Simulation → Diagnose → Edit → Rebuild</strong>

## The workflow in six views

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-pattern-design.png" alt="Pattern stage" width="400"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-sewing.png" alt="Sewing stage" width="400"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/interactive-arrange.png" alt="Fitting stage" width="400"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/avatar-pose-mode.png" alt="Pose stage" width="400"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-arranged.png" alt="Arranged garment" width="400"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped.png" alt="Draped garment" width="400"></p>

## What changes at each stage

| Stage | Human action | Persistent result | Main failure to catch |
| --- | --- | --- | --- |
| Pattern | Draw/edit native Sketcher geometry | PatternPiece references + pattern metadata | Wrong or deleted source geometry |
| Sewing | Select compatible semantic edges and commit seams | Seam identity, direction and correspondence | Stale edge reference or length mismatch |
| Fitting | Drag pieces and snap to arrangement points | Saved piece placements / fitting state | Accidental placement or non-persistent UI-only arrangement |
| Pose | Rotate mannequin joints directly | Skeleton pose / joint rotations | Uncommitted or asymmetrically corrupted pose |
| Simulation | Select target/material/quality, then Run | Derived mesh and solver state | Stale target, unstable simulation, collision failure |
| Diagnose | Inspect stress, six sides and motion | Human verdict and repair decision | A hidden problem masked by one camera angle |

## The human test

A good end-to-end result should be understandable without logs:

1. The pattern reads as an editable garment source.
2. The sewing view makes the seam relationship legible.
3. The fitting view makes the intended garment placement obvious.
4. Pose Mode makes mannequin manipulation obvious.
5. The arranged garment clearly precedes draping.
6. The final garment remains one coherent garment from multiple views.

## Follow the evidence

- [Pattern](01-pattern.md)
- [Sewing](02-sewing.md)
- [Fitting](03-fitting.md)
- [Pose](04-pose.md)
- [Simulation](05-simulation.md)
- [Diagnostics](06-diagnostics.md)
