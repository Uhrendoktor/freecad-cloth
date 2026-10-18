# Copyright (C) 2026 FreeCAD Cloth contributors
"""Regression contracts for FreeCAD Garment hierarchy/link-scope fixes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_pattern_sketch_is_relinked_into_garment_patterns():
    source = (ROOT / "freecad_cloth" / "pattern" / "PatternSketch.py").read_text(encoding="utf-8")
    assert 'link_garment_object(existing, "PatternSketch", document)' in source
    assert 'link_garment_object(sketch, "PatternSketch", document)' in source


def test_fitting_pattern_links_are_explicitly_global_and_visual_sync_is_not_recursive():
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert 'App::PropertyLinkListGlobal", "PatternPieces"' in source
    start = source.index("def _sync_visuals")
    end = source.index("def create_fitting_scene")
    assert "Document.recompute()" not in source[start:end]


def test_fitting_visual_outputs_are_non_dependency_name_references():
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert 'App::PropertyStringList", "ArrangementPointObjects"' in source
    assert 'App::PropertyStringList", "BoundingVolumeObjects"' in source
    assert "scene.ArrangementPointObjects = [obj.Name for obj in point_objects]" in source
    assert "scene.BoundingVolumeObjects = [obj.Name for obj in volume_objects]" in source
    start = source.index("def _migrate_visual_output_references")
    end = source.index("def create_fitting_scene")
    helper = source[start:end]
    assert "removeProperty(name)" in helper
    assert "App::PropertyStringList" in helper


def test_simulation_cross_scope_dependencies_are_global_and_outputs_have_garment_roles():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(
        encoding="utf-8"
    )
    assert 'App::PropertyLinkListGlobal", "ClothPieces"' in source
    assert 'App::PropertyLinkListGlobal", "DrapePanels"' in source
    assert 'App::PropertyLinkGlobal", "DrapeTarget"' in source
    assert 'App::PropertyLinkGlobal", "AvatarProxy"' in " ".join(source.split())
    assert 'link_garment_object(scene, "Simulation", doc)' in source
    assert 'link_garment_object(panel_a, "SimulationOutput", doc)' in source
    assert 'link_garment_object(panel_b, "SimulationOutput", doc)' in source


def test_fitting_marker_tree_groups_outputs_and_prunes_stale_adapters() -> None:
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    assert '_FITTING_MARKER_GROUP_NAME = "ClothFittingMarkers"' in source
    assert '_FITTING_MARKER_GROUP_LABEL = "Fitting / Arrangement Markers (automatic)"' in source
    assert "group.addObject(marker)" in source
    assert "doc.removeObject(name)" in source
    assert "name.startswith(" in source
    assert '"ArrangementPoint_"' in source
    assert 'name.startswith("BoundingVolume_")' in source
    start = source.index("class _FittingProxy")
    end = source.index("COMMANDS", start)
    assert "_sync_visuals(" not in source[start:end]
