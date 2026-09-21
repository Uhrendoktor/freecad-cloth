from pathlib import Path
from types import SimpleNamespace

import pytest

from freecad_cloth.common import ClothDiagnosticsGui
from freecad_cloth.common.ClothDiagnostics import analyze_mesh, export_analysis_data, write_analysis_data
