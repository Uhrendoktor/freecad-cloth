# 08 · Validation and visual evidence

<p align="center"><img src="https://raw.githubusercontent.com/Uhrendoktor/freecad-cloth/refs/heads/docs/screenshots/docs/images/generated/cloth-blanket-motion.gif" alt="Simple blanket collision and drape sequence" width="900"></p>

The project treats validation as both an engineering problem and a human-vision problem.

Every merge to `main` is also a visual-evidence release gate: the publisher rebuilds the documented image set from the merge source and verifies provenance before the run succeeds.

## One canonical execution path

There is one canonical workflow:

<code>.github/workflows/canonical-execution.yml</code>

It covers the main non-GUI checks, real FreeCAD/Xvfb acceptance, garment visual generation, GUI interaction contracts, simulation ladders and visual publication.

The wiki intentionally does not invent a second documentation-only workflow.

## Evidence matrix

| Feature | Human evidence | Executable evidence |
| --- | --- | --- |
| Pattern | Pattern screenshot | Pattern workbench/export smoke + screenshot source |
| Sewing | Sewing screenshot | Sewing smoke/creation + garment E2E |
| Fitting | Interactive Arrange screenshot | <code>freecad_interactive_arrange_acceptance.py</code> |
| Pose | Native Pose Mode screenshot + geometry-only avatar six-side views | <code>freecad_avatar_pose_ui_acceptance.py</code> + avatar acceptance/screenshot |
| Simulation | Cube/mannequin ladder + motion + turntables | PBD ladder, contact diagnostics, E2E and screenshot fixtures |
| Diagnostics | Diagnostic map + six-side views | contact diagnostics + visual sanity/capture validation |
| Persistence | Inspectable FCStd state | domain/persistence tests and acceptance fixtures |
| Invalidation | Visible stale/invalid state | stale-guard and authority regression tests |

## What counts as visual evidence

A valid visual fixture must:

1. actually launch the current code path;
2. capture a non-empty, structurally valid artifact;
3. reject black, white, transparent or effectively uniform GUI captures;
4. represent the requested state rather than a camera-only animation;
5. be traceable to the current canonical execution;
6. be reproducible enough for human comparison.

Pose Mode has an additional interaction-evidence requirement: the published Pose screenshot must be captured after the main window and 3D view are painted, must contain the visible joint overlay and selected-joint gizmo, and must use either the native Coin3D gizmo or the supported visual FreeCAD-geometry fallback. The fallback does not claim direct drag rotation, but it must remain visibly identifiable and usable through the joint selector and precision controls.

## Human review order

When reviewing a garment change, inspect in this order:

<strong>Pattern → Sewing → Arranged → Pose → Motion → Final drape → Six sides → Diagnostics</strong>

This makes upstream errors visible before downstream complexity can hide them.

## Simulation-specific discipline

The simple collision ladder is progressive. Review stops at the first failing rung.

The final garment review also requires multiple side views because visual plausibility from one angle is not sufficient.

## Release gates

A release should be considered visually auditable when:

- current evidence exists for each major user-facing workflow;
- the evidence corresponds to current code;
- generated images are not stale leftovers from an older UI;
- simulation motion contains real state progression;
- final garments are inspected from six sides;
- diagnostics operate on valid/current state;
- known capability boundaries are written down.

See [docs/RELEASE_GATES.md](../RELEASE_GATES.md) and [docs/SIMULATION_REVIEW.md](../SIMULATION_REVIEW.md).

## Why this wiki exists

The purpose is to shorten the distance between a product claim and the evidence needed to judge it.

A human should be able to open a page, look at the feature, inspect the source/test links, and decide whether the behavior shown is actually the behavior the code claims to implement.
