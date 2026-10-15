# Troubleshooting

Use this page by symptom. Find the first authoritative state that is wrong, repair it, and only then debug downstream behavior.

## FreeCAD does not show the Cloth workbenches

Check that the repository directory is installed directly below FreeCAD's user `Mod` directory, then restart FreeCAD.

Both supported FreeCAD loader layouts resolve to the same `freecad_cloth/` implementation package.

## A command is disabled

Check the active document and current selection.

Cloth commands intentionally reject incomplete or ambiguous inputs. Identify the missing prerequisite instead of bypassing the UI by editing internal properties.

## A seam becomes invalid after editing a sketch

Recompute the FreeCAD document and inspect the seam/reference status.

A semantic seam reference is expected to fail closed when its source geometry changes materially. Repair or recreate the reference explicitly. Do not substitute another edge merely because it occupies the same screen position.

## Arrangement looks wrong

Before investigating the solver:

1. Confirm the correct DrapeTarget.
2. Reset the arrangement and place the pieces again.
3. Verify persistent placement/fitting state in the document.
4. Only then proceed to simulation.

This separates fitting problems from physics problems.

## Simulation says the target or scene is stale

Inspect the reported invalidation reason.

Upstream pattern, seam, target or simulation-input changes invalidate dependent derived state. Rebuild or refresh the affected state explicitly and run the simulation again.

The correct fix is to refresh the authoritative input or rebuild derived state, not to bypass the stale check.

## Simulation explodes, collapses or penetrates

Stop at the first visibly invalid state.

Review the [simulation visual-review guide](../developers/SIMULATION_REVIEW.md), starting with the simple collision ladder before the full garment. Do not treat a finite solver exit or one good camera angle as proof of correctness.

## Local results differ from canonical visual evidence

Compare the exact FreeCAD, Triangle, PositionBasedDynamics and source-commit versions.

The canonical workflow publishes evidence from the exact execution it validates. Generated screenshots should not be hand-edited to make them match.
