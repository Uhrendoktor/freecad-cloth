# Troubleshooting

## Workbench does not appear

Check:

1. The repository directory is directly inside FreeCAD's user Mod directory.
2. Init.py and InitGui.py are present at the repository root.
3. FreeCAD has been restarted.
4. The embedded Python runtime is compatible with the supported environment.

## Simulation is blocked

A common cause is stale or missing target-derived state.

Try:

1. Recompute the document.
2. Select or rebuild the DrapeTarget.
3. Check diagnostics for the reason the state is stale.
4. Run again only after the target is current.

## A seam becomes invalid after editing a sketch

This is expected when source topology changed.

Use the explicit seam repair or remap workflow. Do not rely on an automatic guess of the replacement edge.

## The result looks different from CI

Compare the actual FreeCAD, Triangle and Tissu versions first.

The canonical environment is FreeCAD 1.1.0 with Python 3.12. Visual acceptance uses the repository's canonical workflow and generated evidence.

## I changed the GitHub Wiki directly

The repository is the canonical source for human documentation.

Run the canonical GitHub Actions workflow manually with **Wiki operation = import**. Review the resulting pull request, then merge it. The next publish will make the repository copy and live Wiki identical again.
