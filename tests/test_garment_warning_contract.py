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
    assert 'scene.ArrangementPointObjects = [obj.Name for obj in point_objects]' in source
    assert 'scene.BoundingVolumeObjects = [obj.Name for obj in volume_objects]' in source
    start = source.index("def _migrate_visual_output_references")
    end = source.index("def create_fitting_scene")
    helper = source[start:end]
    assert 'removeProperty(name)' in helper
    assert 'App::PropertyStringList' in helper

def test_simulation_cross_scope_dependencies_are_global_and_outputs_have_garment_roles():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    assert 'App::PropertyLinkListGlobal", "ClothPieces"' in source
    assert 'App::PropertyLinkListGlobal", "DrapePanels"' in source
    assert 'App::PropertyLinkGlobal", "DrapeTarget"' in source
    assert 'App::PropertyLinkGlobal", "AvatarProxy"' in source
    assert 'link_garment_object(scene, "Simulation", doc)' in source
    assert 'link_garment_object(panel_a, "SimulationOutput", doc)' in source
    assert 'link_garment_object(panel_b, "SimulationOutput", doc)' in source

def test_simulation_proxy_persists_no_runtime_solver_state():
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

    proxy = SimulationProxy()
    proxy.backend = object()
    proxy.panel_indices = {"panel": (1, 2)}
    proxy.panel_triangles = {"panel": ((0, 1, 2),)}
    proxy.panel_boundary_edges = {"panel": ((0, 1),)}
    proxy.panel_piece_names = {"panel": "Piece"}
    proxy.seam_stitch_pairs = {"seam": ((0, 1),)}
    proxy.source_signature = ("derived",)
    proxy.last_steps = 17
    proxy.collision_surface = object()

    state = proxy.__getstate__()
    assert state == {"schema": 1}
    assert "backend" not in state
    assert "collision_surface" not in state
    assert "seam_stitch_pairs" not in state

    proxy.__setstate__(state)
    assert proxy.backend is None
    assert proxy.panel_indices == {}
    assert proxy.panel_triangles == {}
    assert proxy.panel_boundary_edges == {}
    assert proxy.panel_piece_names == {}
    assert proxy.seam_stitch_pairs == {}
    assert proxy.source_signature is None
    assert proxy.last_steps == 0
    assert proxy.collision_surface is None
