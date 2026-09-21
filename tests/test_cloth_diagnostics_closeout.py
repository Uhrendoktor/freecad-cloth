from pathlib import Path
from types import SimpleNamespace

import pytest

from freecad_cloth.common import ClothDiagnosticsGui
from freecad_cloth.common.ClothDiagnostics import analyze_mesh, export_analysis_data, write_analysis_data

def test_export_is_deterministic_without_model_mutation():
    rest = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    current = ((0.0, 0.0, 0.0), (1.1, 0.0, 0.0), (0.0, 1.1, 0.0))
    result = analyze_mesh(rest, current, ((0, 1, 2),), stretch_limit=0.02)
    first = export_analysis_data(result, "stress")
    second = export_analysis_data(result, "stress")
    assert first == second

def test_export_writer_does_not_change_model_state(tmp_path):
    rest = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    result = analyze_mesh(rest, rest, ((0, 1, 2),))
    document = SimpleNamespace(Name="fixture", Changed=False)
    before = dict(vars(document))
    path = tmp_path / "diagnostics.json"
    write_analysis_data(path, result, "strain")
    assert path.read_text(encoding="utf-8") == export_analysis_data(result, "strain") + "\n"
    assert vars(document) == before
