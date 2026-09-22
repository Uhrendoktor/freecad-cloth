from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_validated_shoulder_edge_mapping():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' in source
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in source


def test_canonical_tunic_keeps_front_shoulder_endpoints_and_four_non_seam_back_supports():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "(0.14 * panel_width, 0.97 * garment_height)" in source
    assert "(0.86 * panel_width, 0.97 * garment_height)" in source
    assert "(0.14 * panel_width, 0.82 * garment_height)" in source
    assert "(0.86 * panel_width, 0.82 * garment_height)" in source
    assert "seam_endpoints = {" in source
    assert "for stitch_pairs in getattr(proxy, \"seam_stitch_pairs\", {}).values()" in source
    assert "available = [index for index in particle_indices if int(index) not in seam_endpoints]" in source
    assert "back_support_pins = authored_back_support_pins(back, back_indices, positions, seam_endpoints)" in source
    assert "pinned = tuple(front_pins) + tuple(back_support_pins)" in source
    assert "scene.PinSelection = [str(i) for i in pinned]" in source
    assert "int(a) in pinned and int(b) in pinned" in source
    assert "scene.PinSelection = [str(i) for i in front_pins]" not in source


def test_canonical_tunic_rejects_known_shoulder_mapping_regressions():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
    assert '((1,1,"TunicRightSide"),(3,3,"TunicRightShoulder"),(6,6,"TunicLeftShoulder"),(7,7,"TunicLeftSide"))' not in audit
