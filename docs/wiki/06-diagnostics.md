# 06 · Diagnostics and visual inspection

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-diagnostics.png" alt="Draped garment diagnostic visualization" width="900"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-front.png" alt="Front" width="260"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-rear.png" alt="Rear" width="260"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-left.png" alt="Left" width="260"></p>

<p align="center"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-right.png" alt="Right" width="260"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-top.png" alt="Top" width="260"><img src="https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/cloth-simulation-draped-bottom.png" alt="Bottom" width="260"></p>

## What the feature is

Diagnostics turn technically valid solver output into human-reviewable evidence.

The visual review deliberately uses more than one camera angle. A single flattering front view can hide penetration, detached panels or inverted geometry.

## Six-side audit

The canonical garment review exposes:

<strong>Front · Rear · Left · Right · Top · Bottom</strong>

For every view, check:

- collision clearance;
- seam continuity;
- detached or exploded panels;
- self-intersection or inversion;
- hem and opening shape;
- whether the garment still reads as one continuous object.

## Diagnostic semantics

Diagnostics should identify the state being inspected and its validity.

Typical evidence includes:

| Evidence | Human question |
| --- | --- |
| Stress map | Where is the current garment highly loaded? |
| Drape sanity | Does the garment remain geometrically plausible? |
| Motion | Did instability appear during stepping or only at the end? |
| Target status | Are these diagnostics based on the current collision target? |
| Stale guard | Is the displayed result known to be current? |

## Fail-closed behavior

Diagnostics must not create confidence from stale state.

When upstream pattern, seam, fitting, pose or target data invalidates the derived simulation, the system should identify that state and require an explicit rebuild/refresh path before presenting a new diagnostic result.

## Human failure review

A diagnostic implementation is suspect when:

- a stress map can be shown for an invalid simulation;
- only the front camera is available for a complex garment result;
- the six-side images silently come from different document states;
- a stale target still produces a convincing-looking map;
- visual and numerical evidence disagree without an explicit explanation.

## Automated evidence

Relevant implementation/tests include:

- <code>freecad_cloth/common/ClothDiagnostics.py</code>
- <code>freecad_cloth/common/ClothDiagnosticsGui.py</code>
- <code>freecad_cloth/common/DrapeVisualSanity.py</code>
- <code>freecad_cloth/common/VisualCaptureValidation.py</code>
- <code>tests/freecad_pbd_contact_diagnostics.py</code>
- <code>tests/freecad_screenshot_source.py</code>

The release policy is documented in [docs/SIMULATION_REVIEW.md](../SIMULATION_REVIEW.md) and [docs/RELEASE_GATES.md](../RELEASE_GATES.md).
