# FreeCAD Cloth visual wiki

This is the feature manual and audit index for FreeCAD Cloth.

The goal is not to repeat every engineering note. The goal is to let a human answer, feature by feature:

- What is this?
- What would I see in FreeCAD?
- What persistent state should exist afterward?
- What does failure look like?
- Where is the implementation?
- Which automated test or acceptance fixture supports the claim?
- Which generated image or animation should I inspect?

## Feature index

| Page | Feature | Primary visual proof |
| --- | --- | --- |
| [00 · Overview](00-overview.md) | Complete garment workflow | Pattern → sewn → arranged → posed → draped |
| [01 · Pattern](01-pattern.md) | Native 2D pattern authoring | <code>cloth-pattern-design.png</code> |
| [02 · Sewing](02-sewing.md) | Semantic sewing and correspondence | <code>cloth-sewing.png</code> |
| [03 · Fitting](03-fitting.md) | Direct 3D arrangement and snapping | <code>interactive-arrange.png</code> + arranged garment |
| [04 · Pose](04-pose.md) | Human mannequin Pose Mode | <code>avatar-pose-mode.png</code> + avatar views |
| [05 · Simulation](05-simulation.md) | Cloth physics and draping | arranged/draped turntables + motion GIF |
| [06 · Diagnostics](06-diagnostics.md) | Visual diagnosis and six-side review | diagnostic map + six views |
| [07 · Data model](07-data-model.md) | Persistence and authority model | architecture diagram + inspectable state |
| [08 · Validation](08-validation.md) | CI, acceptance and visual evidence | generated evidence matrix |

## Visual evidence convention

Images in these pages use the generated evidence published by the canonical workflow:

<code>https://github.com/Uhrendoktor/freecad-cloth/raw/refs/heads/docs/screenshots/docs/images/generated/</code>

That branch is a publication target. The current source code and canonical workflow remain authoritative.

## Audit vocabulary

<strong>Authoritative</strong> means the data a user can edit and save in the FreeCAD document.

<strong>Derived</strong> means data rebuilt from authoritative inputs, such as simulation particles or generated collision surfaces.

<strong>Transient</strong> means viewport-only interaction state, such as a drag preview or temporary selection.

<strong>Fail closed</strong> means an invalid or stale input is surfaced as invalid instead of being silently guessed or substituted.

## Reading order

Start with [00 · Overview](00-overview.md), then inspect the individual feature pages. Finish with [07 · Data model](07-data-model.md) and [08 · Validation](08-validation.md) when you want to audit how the visuals connect back to persistent state and automated checks.

## Human acceptance rule

A page is visually demonstrated when a reader can identify the expected UI or geometry in the supplied evidence without relying on narration alone.
