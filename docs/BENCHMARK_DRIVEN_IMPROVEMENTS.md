# Benchmark-driven workbench improvements

> Historical analysis: this document records the benchmark study associated with closed issue #478 and run 221. It is not a live task list or current performance baseline. Re-run the benchmark on the current main before using any number for a decision.



## Baseline

| Workbench | Nonblank LOC | Registered commands | Related test files | Initialize median (ms) |
| --- | ---: | ---: | ---: | ---: |
| Pattern | 2,792 | 16 | 10 | 0.327 |
| Sewing | 2,035 | 32 | 12 | 0.364 |
| Simulation | 2,436 | 13 | 28 | 0.343 |

The measured initialization cost is below 0.4 ms for every workbench. It is therefore not a useful optimization target at this stage.

## Historical improvement proposals

### 1. Protect the Sewing public command surface

**Measured signal:** Sewing exposes 32 registered commands with only 12 related test files, while Simulation has 13 commands with 28 related test files. Sewing therefore has the thinnest test-to-command coverage of the three workbenches.

**Change:** add a deterministic command-surface regression test covering the complete Sewing command inventory across core sewing, sewing-network, fitting, and avatar registration. The test must fail on a missing, duplicate, or drifted command name before GUI acceptance is reached.

**Expected effect:** command registration drift becomes a fast headless failure instead of a GUI-only regression.

**Regression boundary:** this checks the public command contract only; it does not execute FreeCAD GUI commands or alter workbench behavior.

### 2. Keep Sewing discoverability progressive

**Measured signal:** 32 registered commands are concentrated in one workbench, more than twice Simulation's 13-command surface.

**Change:** retain the existing three primary menu groups and a small toolbar subset; new Sewing commands must land in a named group and must not silently expand the toolbar.

**Expected effect:** the command surface scales without turning the primary toolbar into a command catalog.

**Regression boundary:** menu/toolbar composition remains a UI-contract test and does not constrain internal semantic APIs.

### 3. Avoid speculative startup micro-optimization

**Measured signal:** Pattern 0.327 ms, Sewing 0.364 ms, Simulation 0.343 ms median initialization over seven samples.

**Change:** do not refactor workbench initialization for speed until a future benchmark shows a material startup regression. Reuse the existing benchmark artifact for before/after comparisons whenever command registration changes.

**Expected effect:** effort stays on release-relevant UX and regression coverage instead of sub-millisecond noise.

**Regression boundary:** no runtime behavior change; this is an explicit decision gate for future optimization work.

## Adoption rule

Each follow-up optimization must report its measured baseline and replacement measurement. No performance claim should be made from implementation size or command count alone.
