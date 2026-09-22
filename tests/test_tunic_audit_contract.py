from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_tunic_uses_independent_front_back_semantic_edge_ids():
    source = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'front_edge_ids = tuple(str(value) for value in getattr(front.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'back_edge_ids = tuple(str(value) for value in getattr(back.Sketch, "SemanticEdgeIds", ()) or ())' in source
    assert 'front_edge_ids[1], back_edge_ids[1], "TunicRightSide"' in source
    assert 'front_edge_ids[2], back_edge_ids[2], "TunicRightShoulder"' in source
    assert 'front_edge_ids[5], back_edge_ids[5], "TunicLeftShoulder"' in source
    assert 'front_edge_ids[6], back_edge_ids[6], "TunicLeftSide"' in source
    assert 'f"{front.PieceId}:edge:1", f"{back.PieceId}:edge:1"' not in source

def test_canonical_tunic_pins_only_one_side_of_sewn_shoulders():
    source = (ROOT / "tests" / "freecad_screenshot_source.py").read_text(encoding="utf-8")
    assert "scene.PinSelection = [str(i) for i in front_pins]" in source
    assert "scene.PinSelection = [str(i) for i in front_pins + back_pins]" not in source
    assert "the back panel must follow through the" in source

def test_canonical_tunic_rejects_integer_seam_mapping_regression():
    audit = (ROOT / "tests" / "freecad_tunic_audit.py").read_text(encoding="utf-8")
    assert 'f"{front.PieceId}:edge:1", f"{back.PieceId}:edge:1", "TunicRightSide"' in audit
    assert 'f"{front.PieceId}:edge:2", f"{back.PieceId}:edge:2", "TunicRightShoulder"' in audit
    assert 'f"{front.PieceId}:edge:5", f"{back.PieceId}:edge:5", "TunicLeftShoulder"' in audit
    assert 'f"{front.PieceId}:edge:6", f"{back.PieceId}:edge:6", "TunicLeftSide"' in audit
    assert '(1,1,"TunicRightSide")' not in audit

def test_canonical_tunic_source_rewrite_compiles_headless():
    import ast

    audit_path = ROOT / "tests" / "freecad_tunic_audit.py"
    audit_source = audit_path.read_text(encoding="utf-8")
    module = ast.parse(audit_source, filename=str(audit_path))
    replacements = None
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "replacements"
            for target in node.targets
        ):
            replacements = ast.literal_eval(node.value)
            break
    assert replacements is not None

    seam_keys = [key for key in replacements if "for edge_a, edge_b, seam_id" in key]
    assert seam_keys == [
        '    for edge_a, edge_b, seam_id in ((2,2,"TunicRightShoulder"),(5,5,"TunicLeftShoulder")):'
    ]
    assert replacements[seam_keys[0]].startswith("    front_edge_ids = ")

    source_path = ROOT / "tests" / "freecad_screenshot_source.py"
    source = source_path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        assert old in source
        source = source.replace(old, new, 1)
    compile(source, str(source_path), "exec")
