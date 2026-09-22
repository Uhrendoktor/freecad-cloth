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


def test_simulation_cross_scope_dependencies_are_global_and_outputs_have_garment_roles():
    source = (ROOT / "freecad_cloth" / "simulation" / "SimulationObjects.py").read_text(encoding="utf-8")
    assert 'App::PropertyLinkListGlobal", "ClothPieces"' in source
    assert 'App::PropertyLinkListGlobal", "DrapePanels"' in source
    assert 'App::PropertyLinkGlobal", "DrapeTarget"' in source
    assert 'App::PropertyLinkGlobal", "AvatarProxy"' in source
    assert 'link_garment_object(scene, "Simulation", doc)' in source
    assert 'link_garment_object(panel_a, "SimulationOutput", doc)' in source
    assert 'link_garment_object(panel_b, "SimulationOutput", doc)' in source

def test_fitting_proxy_execute_does_not_sync_derived_visuals():
    source = (ROOT / "freecad_cloth" / "avatar" / "FittingCommands.py").read_text(encoding="utf-8")
    start = source.index("class _FittingProxy:")
    end = source.index("\n\nCOMMANDS =", start)
    execute = source[start:end]
    assert "def execute(self, obj):" in execute
    execute_body = execute.split("def execute(self, obj):", 1)[1]
    assert "_sync_visuals(" not in execute_body
