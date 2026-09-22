"""Real-FreeCAD smoke coverage for staged sewing Preview/Commit/Cancel."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import FreeCAD as App
import FreeCADGui as Gui

from freecad_cloth.pattern.PatternModel import PatternPiece
from freecad_cloth.pattern.PatternObjects import add_pattern_piece
from freecad_cloth.sewing.SewingCommands import create_mn_sewing_from_selection, create_seam_from_selection
from freecad_cloth.sewing.SewingCreationGui import SewingCreationTaskPanel


LOG_PATH = Path(os.environ.get("CLOTH_SEWING_SMOKE_LOG", ROOT / "artifacts" / "sewing-creation-smoke.log"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG = []


def record(message):
    LOG.append(message)
    print(message, flush=True)


def select_edges(*items):
    Gui.Selection.clearSelection()
    for obj, edge in items:
        Gui.Selection.addSelection(obj, "Edge%d" % (int(edge) + 1))


doc = App.newDocument("SewingCreationSmoke")
piece_a = add_pattern_piece(doc, PatternPiece("SmokeA", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-a"))
piece_b = add_pattern_piece(doc, PatternPiece("SmokeB", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-b"))
piece_c = add_pattern_piece(doc, PatternPiece("SmokeC", [(0, 0), (100, 0), (100, 100), (0, 100)], id="smoke-c"))
doc.recompute()

before = {obj.Name for obj in doc.Objects}
select_edges((piece_a, 0), (piece_b, 0))
panel = SewingCreationTaskPanel("seam")
assert any(getattr(obj, "SeamId", "") for obj in panel.session.created), "1:1 preview did not create a seam"
assert "Preview valid" in panel.feedback.text()
record("preview-1to1=passed")
panel.accept()
assert any(getattr(obj, "SeamId", "") for obj in doc.Objects if obj.Name not in before), "1:1 commit lost seam"
record("commit-1to1=passed")

cancel_before = {obj.Name for obj in doc.Objects}
select_edges((piece_a, 1), (piece_b, 1))
cancel_panel = SewingCreationTaskPanel("seam")
assert any(getattr(obj, "SeamId", "") for obj in cancel_panel.session.created)
cancel_panel.reject()
assert {obj.Name for obj in doc.Objects} == cancel_before, "cancel persisted preview objects"
record("cancel-1to1=passed")

same_piece_before = {obj.Name for obj in doc.Objects}
select_edges((piece_a, 0), (piece_a, 1))
invalid_panel = SewingCreationTaskPanel("seam")
assert "Preview rejected" in invalid_panel.feedback.text()
assert "different pattern pieces" in invalid_panel.feedback.text()
assert {obj.Name for obj in doc.Objects} == same_piece_before
invalid_panel.reject()
assert {obj.Name for obj in doc.Objects} == same_piece_before
record("invalid-same-piece-preview=passed")

mn_before = {obj.Name for obj in doc.Objects}
select_edges((piece_a, 0), (piece_b, 1), (piece_c, 2))
invalid_mn_panel = SewingCreationTaskPanel("mn")
assert "Preview rejected" in invalid_mn_panel.feedback.text()
assert "two different pattern pieces" in invalid_mn_panel.feedback.text()
assert {obj.Name for obj in doc.Objects} == mn_before
invalid_mn_panel.reject()
assert {obj.Name for obj in doc.Objects} == mn_before
record("invalid-mn-partition-preview=passed")

select_edges((piece_a, 0), (piece_a, 1), (piece_b, 0), (piece_b, 1))
mn_panel = SewingCreationTaskPanel("mn")
assert any(getattr(obj, "SewingType", "") == "SewingNetwork" for obj in mn_panel.session.created)
record("preview-mn=passed")
mn_panel.accept()
networks = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"]
assert networks and networks[-1].Status == "Valid", "M:N commit did not leave a valid network"
record("commit-mn=passed")

try:
    pass
finally:
    LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
    Gui.Selection.clearSelection()
    if App.ActiveDocument is not None and App.ActiveDocument.Name == doc.Name:
        App.closeDocument(doc.Name)
    print("sewing-creation-smoke=completed", flush=True)
