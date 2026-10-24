# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for FreeCAD Garment hierarchy and link-scope invariants."""

from pathlib import Path

from support.assertions import require

ROOT = Path(__file__).resolve().parents[1]


def test_native_pattern_sketch_is_relinked_into_garment_patterns() -> None:
    """Require native Sketcher objects to be linked into the canonical garment tree."""
    source = (ROOT / "freecad_cloth" / "pattern" / "PatternSketch.py").read_text(encoding="utf-8")
    require(
        'link_garment_object(existing, "PatternSketch", document)' in source,
        "Existing sketches must be relinked into the Garment hierarchy.",
    )
    require(
        'link_garment_object(sketch, "PatternSketch", document)' in source,
        "New sketches must be linked into the Garment hierarchy.",
    )


def test_fitting_pattern_links_are_explicitly_global_and_visual_sync_is_not_recursive() -> None:
    """Keep cross-scope pattern links explicit and visual synchronization non-recursive."""
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        'App::PropertyLinkListGlobal", "PatternPieces"' in source,
        "FittingScene pattern references must be document-global links.",
    )
    start = source.index("def _sync_visuals")
    end = source.index("def create_fitting_scene")
    require(
        "Document.recompute()" not in source[start:end],
        "Visual synchronization must not recursively recompute the document.",
    )


def test_fitting_visual_outputs_are_non_dependency_name_references() -> None:
    """Persist generated markers by name instead of retaining dependency links."""
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        'App::PropertyStringList", "ArrangementPointObjects"' in source,
        "Arrangement point output references must be string lists.",
    )
    require(
        'App::PropertyStringList", "BoundingVolumeObjects"' in source,
        "Bounding-volume output references must be string lists.",
    )
    require(
        "_migrate_visual_output_references" not in source,
        "Pre-release visual-link migration must not remain as a second path.",
    )


def test_simulation_cross_scope_dependencies_are_global_and_outputs_have_garment_roles() -> None:
    """Keep simulation inputs document-global and output containers classified by role."""
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    require(
        'App::PropertyLinkListGlobal", "ClothPieces"' in source,
        "Simulation cloth-piece inputs must be document-global links.",
    )
    require(
        'App::PropertyLinkListGlobal", "DrapePanels"' in source,
        "Simulation output panels must be document-global links.",
    )
    require(
        'App::PropertyLinkGlobal", "DrapeTarget"' in source,
        "DrapeTarget must remain the simulation's sole collision authority.",
    )
    require(
        'App::PropertyLinkGlobal", "AvatarProxy"' not in " ".join(source.split()),
        "Simulation must not persist a duplicate AvatarProxy reference.",
    )
    require(
        "create_avatar_collision" not in source,
        "Simulation must not construct a second AvatarCollision object.",
    )
    require(
        'link_garment_object(scene, "Simulation", doc)' in source,
        "The scene must have the Simulation garment role.",
    )
    require(
        'link_garment_object(panel_a, "SimulationOutput", doc)' in source,
        "Panel A must have the SimulationOutput garment role.",
    )
    require(
        'link_garment_object(panel_b, "SimulationOutput", doc)' in source,
        "Panel B must have the SimulationOutput garment role.",
    )


def test_fitting_marker_tree_groups_outputs_and_prunes_stale_adapters() -> None:
    """Keep automatic arrangement markers grouped and stale adapters pruned."""
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    require(
        '_FITTING_MARKER_GROUP_NAME = "ClothFittingMarkers"' in source,
        "Fitting markers must have a dedicated group.",
    )
    require(
        '_FITTING_MARKER_GROUP_LABEL = "Fitting / Arrangement Markers (automatic)"' in source,
        "The marker group must carry its expected display label.",
    )
    require("group.addObject(marker)" in source, "Generated markers must enter the marker group.")
    require("doc.removeObject(name)" in source, "Stale marker objects must be removed.")
    require("name.startswith(" in source, "Marker cleanup must filter by stable object-name prefix.")
    require('"ArrangementPoint_"' in source, "Arrangement marker names must use their stable prefix.")
    require(
        'name.startswith("BoundingVolume_")' in source,
        "Bounding-volume marker cleanup must use its stable prefix.",
    )
    start = source.index("class _FittingProxy")
    end = source.index("COMMANDS", start)
    require(
        "_sync_visuals(" not in source[start:end],
        "The fitting proxy must not recursively invoke visual synchronization.",
    )
