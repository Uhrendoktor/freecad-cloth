from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_simulation_arrange_fit_bridge_is_user_visible_and_target_authoritative():
    handoff = (ROOT / "freecad_cloth" / "simulation" / "FittingHandoff.py").read_text(encoding="utf-8")
    quality = (ROOT / "freecad_cloth" / "simulation" / "SimulationQualityGui.py").read_text(encoding="utf-8")
    acceptance = (ROOT / "tests" / "freecad_simulation_quality_acceptance.py").read_text(encoding="utf-8")
    assert "open_arrange_fit_from_simulation" in handoff
    assert 'fitting.DrapeTarget = target' in handoff
    assert 'QPushButton("Arrange / Fit…")' in quality
    assert "Refresh target" in quality
    assert "Reset arrangement" in quality
    assert "arrange_fit" in quality
    assert "target-recovery" in acceptance


def test_seam_color_lifecycle_refresh_is_global_and_stable():
    view = (ROOT / "freecad_cloth" / "sewing" / "SewingView.py").read_text(encoding="utf-8")
    pattern = (ROOT / "freecad_cloth" / "pattern" / "PatternCommands.py").read_text(encoding="utf-8")
    sewing = (ROOT / "freecad_cloth" / "sewing" / "SewingCommands.py").read_text(encoding="utf-8")
    sewing_objects = (ROOT / "freecad_cloth" / "sewing" / "SewingObjects.py").read_text(encoding="utf-8")
    assert "def refresh_seam_colors" in view
    assert "hashlib.sha256" in view
    assert "refresh_seam_colors()" in pattern
    assert "refresh_seam_colors(document)" in sewing
    assert "refresh_seam_colors(obj.Document)" in sewing_objects
