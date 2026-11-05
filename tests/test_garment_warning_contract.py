# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for FreeCAD Garment hierarchy and link-scope invariants."""

from pathlib import Path

from support.assertions import require

ROOT = Path(__file__).resolve().parents[1]


def test_native_pattern_sketch_is_relinked_into_garment_patterns() -> None:
    """Require native Sketcher objects to be linked into the canonical garment tree."""
    source = (ROOT / "freecad_cloth" / "pattern" / "PatternSketch.py").read_text(encoding="utf-8")
    require(
        condition='link_garment_object(existing, "PatternSketch", document)' in source,
        message="Existing sketches must be relinked into the Garment hierarchy.",
    )
    require(
        condition='link_garment_object(sketch, "PatternSketch", document)' in source,
        message="New sketches must be linked into the Garment hierarchy.",
    )


def test_fitting_pattern_links_are_explicitly_global_and_visual_sync_is_not_recursive() -> None:
    """Keep cross-scope pattern links explicit and visual synchronization non-recursive."""
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        condition='App::PropertyLinkListGlobal", "PatternPieces"' in source,
        message="FittingScene pattern references must be document-global links.",
    )
    start = source.index("def _sync_visuals")
    end = source.index("def create_fitting_scene")
    require(
        condition="Document.recompute()" not in source[start:end],
        message="Visual synchronization must not recursively recompute the document.",
    )


def test_fitting_visual_outputs_are_non_dependency_name_references() -> None:
    """Persist generated markers by name instead of retaining dependency links."""
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        condition='App::PropertyStringList", "ArrangementPointObjects"' in source,
        message="Arrangement point output references must be string lists.",
    )
    require(
        condition='App::PropertyStringList", "BoundingVolumeObjects"' in source,
        message="Bounding-volume output references must be string lists.",
    )
    require(
        condition="_migrate_visual_output_references" not in source,
        message="Pre-release visual-link migration must not remain as a second path.",
    )


def test_simulation_cross_scope_dependencies_are_global_and_outputs_have_garment_roles() -> None:
    """Keep simulation inputs document-global and output containers classified by role."""
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(
        encoding="utf-8"
    )
    require(
        condition='App::PropertyLinkListGlobal", "ClothPieces"' in source,
        message="Simulation cloth-piece inputs must be document-global links.",
    )
    require(
        condition='App::PropertyLinkListGlobal", "DrapePanels"' in source,
        message="Simulation output panels must be document-global links.",
    )
    require(
        condition='App::PropertyLinkGlobal", "DrapeTarget"' in source,
        message="DrapeTarget must remain the simulation's sole collision authority.",
    )
    require(
        condition='App::PropertyLinkGlobal", "AvatarProxy"' not in " ".join(source.split()),
        message="Simulation must not persist a duplicate AvatarProxy reference.",
    )
    require(
        condition="create_avatar_collision" not in source,
        message="Simulation must not construct a second AvatarCollision object.",
    )
    require(
        condition='link_garment_object(scene, "Simulation", doc)' in source,
        message="The scene must have the Simulation garment role.",
    )
    require(
        condition='link_garment_object(panel_a, "SimulationOutput", doc)' in source,
        message="Panel A must have the SimulationOutput garment role.",
    )
    require(
        condition='link_garment_object(panel_b, "SimulationOutput", doc)' in source,
        message="Panel B must have the SimulationOutput garment role.",
    )


def test_fitting_marker_tree_groups_outputs_and_prunes_stale_adapters() -> None:
    """Keep automatic arrangement markers grouped and stale adapters pruned."""
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        condition='_FITTING_MARKER_GROUP_NAME = "ClothFittingMarkers"' in source,
        message="Fitting markers must have a dedicated group.",
    )
    require(
        condition=(
            '_FITTING_MARKER_GROUP_LABEL = "Fitting / Arrangement Markers (automatic)"' in source
        ),
        message="The marker group must carry its expected display label.",
    )
    require(
        condition="group.addObject(marker)" in source,
        message="Generated markers must enter the marker group.",
    )
    require(
        condition="doc.removeObject(name)" in source,
        message="Stale marker objects must be removed.",
    )
    require(
        condition="name.startswith(" in source,
        message="Marker cleanup must filter by stable object-name prefix.",
    )
    require(
        condition='"ArrangementPoint_"' in source,
        message="Arrangement marker names must use their stable prefix.",
    )
    require(
        condition='name.startswith("BoundingVolume_")' in source,
        message="Bounding-volume marker cleanup must use its stable prefix.",
    )
    start = source.index("class _FittingProxy")
    end = source.index("COMMANDS", start)
    require(
        condition="_sync_visuals(" not in source[start:end],
        message="The fitting proxy must not recursively invoke visual synchronization.",
    )
