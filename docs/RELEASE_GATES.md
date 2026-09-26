# Release gates

“Complete” means the repository is installable, understandable, testable and visually inspectable. It does not mean feature parity with a commercial garment suite.

## Required gates

| Gate | Evidence |
|---|---|
| Installation | [INSTALLATION.md](INSTALLATION.md) describes user and developer setup |\n| Documentation contracts | `tests/test_documentation_contract.py` validates internal docs links, current command IDs/UI labels, runtime prerequisites, stable media references, and capability-boundary wording |
| User workflow | [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) covers Pattern → Sewing → Arrange → Simulate → Iterate |
| Example ladder | [EXAMPLES.md](EXAMPLES.md) contains basic and advanced paths |
| Python quality | canonical non-GUI test set and compileall pass |
| Native FreeCAD GUI | Xvfb workbench smoke tests pass |
| Sewing visuals | semantic seams render in 2D and 3D with deterministic colors |
| Simulation geometry | drape metrics, connected-component checks and mesh spike/footprint sanity pass |
| Turntable integrity | 73-frame arranged and final-drape turntables pass |
| Motion evidence | simulation motion GIF contains multiple simulation states, not only camera rotation |
| Material presentation | persisted fabric color, transparency, roughness and specular controls exist; viewport color is applied |
| Persistence | save/reload does not lose semantic seam, material or target state |
| Invalidation | upstream pattern/target edits block stale simulation/export until explicit repair/rebuild |
| Packaging | FreeCAD bootstrap files and repository layout remain valid for direct `Mod` installation |
| Open-source project hygiene | contribution, security, code-of-conduct, issue-template and pull-request entry points exist; dependency updates are automated |
| Repository hygiene | stale agent branches and obsolete workflow runs follow an explicit retention policy |

## Feature boundary

The project deliberately does not claim full CLO-like parity. Advanced capabilities such as grading/nesting, construction hardware, richer avatar posing, pressure/fit maps and calibration-grade material libraries remain named roadmap work.

A release should not mark those features “complete” merely because the end-to-end tunic path is green.

## Visual evidence rule

A screenshot assertion is fail-closed when the captured artifact is missing, corrupt, empty, or structurally inconsistent with the source semantics. Camera-only rotation does not count as simulation-motion evidence.

## Change rule

Every new user-visible workflow should add or extend an executable example and at least one deterministic automated assertion before it is described as complete in README or release records.
