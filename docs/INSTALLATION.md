# Installation

FreeCAD Cloth is a native FreeCAD workbench extension. The repository itself is the source tree; installation places the repository directory directly below FreeCAD's user Mod directory.

## Requirements

### User prerequisites

- A supported FreeCAD build with an embedded Python 3.12 or newer runtime for the current project baseline.
- A FreeCAD GUI session.
- The dependency triangle==20250106 available to the same Python environment used by FreeCAD for the project.
- Tissu is optional. The deterministic XPBD CPU backend remains the correctness fallback when the optional Tissu package is not available.

The canonical validation environment is the FreeCAD 1.1.0 / Python 3.12 container recorded in .github/workflows/canonical-execution.yml. The repository currently targets Python 3.12+ in pyproject.toml.

### Find the user Mod directory

From FreeCAD's Python console, this prints the user application-data directory:

    App.getUserAppDataDir()

The installation target is the Mod subdirectory of that location. If your FreeCAD package uses a platform-specific user-data layout, use the path reported by FreeCAD rather than guessing it.

## User installation

1. Download or clone the repository.
2. Copy the complete repository directory into the FreeCAD user Mod directory, for example:
   <FreeCAD user data>/Mod/freecad-cloth/
3. Keep Init.py and InitGui.py at the repository root. Do not put them below another directory level.
4. Ensure triangle==20250106 is installed for the Python runtime that FreeCAD actually uses.
5. Restart FreeCAD.
6. Confirm that **Cloth Pattern**, **Cloth Sewing**, and **Cloth Simulation** appear in the workbench selector.

For an existing installation, remove the previous freecad-cloth directory before replacing it so stale Python modules are not left on the module search path.

## First successful result

Do not start with the full tunic. First run the **Blanket over Cube** example in [EXAMPLES.md](EXAMPLES.md). A successful smoke test means the Cloth workbenches load, a native Sketcher pattern can become a PatternPiece, a persistent FreeCAD-geometry DrapeTarget can be created for the cube, the cloth mesh remains finite, and the simulation changes the cloth position.

The canonical visual fixture is tests/freecad_visual_examples.py; it is the repository's authoritative installation smoke test because it also checks mesh structure, material presentation and real viewport motion.

After the blanket result is working, continue with the tunic path in [EXAMPLES.md](EXAMPLES.md) and then use [USER_GUIDE.md](USER_GUIDE.md) as the day-to-day reference.

## Developer setup

The dependency used by the canonical workflow is installed with:

    python3 -m pip install triangle==20250106

Run that in the same Python 3.12 environment used for the FreeCAD development/CI runtime. The repository's non-GUI tests are normal Python scripts; the real FreeCAD GUI/Xvfb acceptance path is the single canonical workflow in .github/workflows/canonical-execution.yml.

Do not create a second workflow for a one-off documentation or GUI check.

## Troubleshooting and recovery

**The workbenches do not appear**

Check that the repository directory is directly below the FreeCAD user Mod directory, that Init.py and InitGui.py are still at the repository root, and restart FreeCAD. If an older installation was present, remove the old directory and reinstall it.

**Pattern creation fails with a Triangle/import error**

Install triangle==20250106 into the Python environment used by FreeCAD, then restart FreeCAD. A successful import in a separate system Python does not prove that the embedded FreeCAD runtime can import it.

**A seam becomes invalid after editing a Sketcher pattern**

Recompute the document and use **Cloth Sewing → Repair Seam** only for an existing semantic seam whose referenced edge still exists. If the semantic edge no longer exists, recreate the seam against the intended edge; Cloth does not silently retarget it.

**The Drape Target is stale, unbuilt, disabled or invalid**

Open **Edit Drape Target**, confirm the Provider and Source, then use **Apply & Refresh**. The simulation intentionally blocks **Step** and **Run 30** until the target is valid. Do not bypass the stale state by continuing with an old collision mesh.

**Simulation has no cloth or the scene is empty**

Select the intended PatternPiece objects and verify the simulation scene's ClothPieces links in the FreeCAD Property Editor. The quality task panel does not substitute for missing cloth-piece links.

**The tunic intersects the mannequin**

Do not assume the project currently performs automatic CLO-style garment snapping. Arrangement is explicit: use the fitting scene's arrangement points or direct persistent piece placements, verify the DrapeTarget source, and refresh it after source changes. The validated tunic fixture uses authored shoulder pinning for its current acceptance path; it does not establish a general global-pin or automatic-snap requirement.

**Local screenshots differ from CI**

Use the same FreeCAD/Triangle/Tissu versions recorded by the canonical workflow before comparing screenshots. Published README media is generated from validated CI artifacts; do not manually replace those assets with ad-hoc captures.

## Current release boundary

The project is currently at package version 0.1.0 with the P0 end-to-end workflow validated. It does not claim full commercial garment-suite parity. Capabilities listed in the roadmap as P1 or Production work should be treated as future scope unless their own acceptance evidence says otherwise.
