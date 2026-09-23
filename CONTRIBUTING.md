# Contributing

FreeCAD Cloth keeps FreeCAD's document model authoritative and keeps solver state rebuildable.

## Development rules

- Put implementation modules below `freecad_cloth/`.
- Keep native Sketcher geometry authoritative for editable pattern geometry.
- Keep semantic seams independent from generated mesh topology.
- Do not silently retarget invalid semantic references.
- Add a deterministic test for every bug fix.
- Add or extend a visual fixture for user-facing geometry, selection or simulation changes.
- Reuse `.github/workflows/canonical-execution.yml`; do not add parallel CI workflows for the same acceptance path.
- Do not weaken an assertion to make a visual or solver failure disappear.

## Local checks

Run the focused Python tests first, then the FreeCAD/Xvfb scenario relevant to the change. The exact canonical list is maintained in the single GitHub Actions workflow.

For visual work, inspect both the generated image and the structured log/metrics. A green process exit without evidence is not considered sufficient.

## Pull requests

Describe the user-visible behavior, the authoritative source of the state, the regression test and any remaining roadmap limitation. Avoid describing commercial feature parity unless the behavior is actually implemented and tested.
