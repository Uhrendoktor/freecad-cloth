from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_validated_shoulder_edge_mapping():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' in source
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_known_shoulder_mapping_regressions():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit


def test_canonical_tunic_enforces_authoritative_solver_seam_gate():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'if max_seam_gap > 35.0:' in audit
    assert '_seam_coherence(panels, seam_records, proxy=scene.Proxy)' in audit
    assert 'write_drape_metrics(' in audit
    assert 'seam_records=seam_records,\\n        proxy=proxy,' in audit
    assert 'tunic seam-gate injection anchor missing from canonical source' in audit
    assert 'authoritative-seam-max-gap-mm=%.2f' in audit
