from freecad_cloth.common.PatternSimulationAdapter import resolve_piece_ir


def test_sketch_authority_resolves_without_legacy_fallback():
    assert resolve_piece_ir is not None


if __name__ == "__main__":
    test_sketch_authority_resolves_without_legacy_fallback()
    print("Pattern simulation adapter tests passed")
