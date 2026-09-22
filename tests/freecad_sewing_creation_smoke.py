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
from freecad_cloth.sewing.SewingCreationGui import SewingCreationTaskPanel, SewingCreationSession


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
piece_a = add_pattern_piece(doc, PatternPiece("SmokeA", [(0, 0), (100, 0), (100, 80), (0, 80)], id="smoke-a"))
piece_b = add_pattern_piece(doc, PatternPiece("SmokeB", [(0, 0), (100, 0), (100, 80), (0, 80)], id="smoke-b"))
piece_c = add_pattern_piece(doc, PatternPiece("SmokeC", [(0, 0), (100, 0), (100, 80), (0, 80)], id="smoke-c"))
doc.recompute()

before = {obj.Name for obj in doc.Objects}
select_edges((piece_a, 0), (piece_b, 0))
session = SewingCreationSession(doc, Gui, "Create Seam", create_seam_from_selection)
created = session.preview()
assert any(getattr(obj, "SeamId", "") for obj in created), "1:1 preview did not create a seam"
record("preview-1to1=passed")
session.commit()
assert any(getattr(obj, "SeamId", "") for obj in doc.Objects if obj.Name not in before), "1:1 commit lost seam"
record("commit-1to1=passed")

cancel_before = {obj.Name for obj in doc.Objects}
select_edges((piece_a, 1), (piece_b, 1))
cancel_session = SewingCreationSession(doc, Gui, "Create Seam", create_seam_from_selection)
cancel_session.preview()
assert any(getattr(obj, "SeamId", "") for obj in cancel_session.created)
cancel_session.cancel()
assert {obj.Name for obj in doc.Objects} == cancel_before, "cancel persisted preview objects"
record("cancel-1to1=passed")

select_edges((piece_a, 0), (piece_a, 1))
invalid_panel = SewingCreationTaskPanel.__new__(SewingCreationTaskPanel)
invalid_panel.feedback = type("Label", (), {"setText": lambda self, value: setattr(self, "text", value), "setStyleSheet": lambda self, value: None})()
invalid_panel.commit_button = type("Button", (), {"setEnabled": lambda self, value: setattr(self, "enabled", value)})()
invalid_panel._show_error(ValueError("a sewing relationship must connect two different pattern pieces"))
assert "Adjust the selection" in invalid_panel.feedback.text
record("invalid-same-piece-feedback=passed")

select_edges((piece_a, 0), (piece_b, 1), (piece_c, 2))
mn_before = {obj.Name for obj in doc.Objects}
mn_panel = SewingCreationTaskPanel.__new__(SewingCreationTaskPanel)
mn_panel.feedback = type("Label", (), {"setText": lambda self, value: setattr(self, "text", value), "setStyleSheet": lambda self, value: None})()
mn_panel.commit_button = type("Button", (), {"setEnabled": lambda self, value: setattr(self, "enabled", value)})()
mn_panel._show_error(ValueError("select edges from exactly two pattern pieces"))
assert "Preview rejected" in mn_panel.feedback.text
assert {obj.Name for obj in doc.Objects} == mn_before
record("invalid-mn-partition-feedback=passed")

select_edges((piece_a, 0), (piece_a, 1), (piece_b, 0))
mn_session = SewingCreationSession(doc, Gui, "Create M:N Sewing", create_mn_sewing_from_selection)
mn_created = mn_session.preview()
assert any(getattr(obj, "SewingType", "") == "SewingNetwork" for obj in mn_created)
record("preview-mn=passed")
mn_session.commit()
networks = [obj for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"]
assert networks and networks[-1].Status == "Valid", "M:N commit did not leave a valid network"
record("commit-mn=passed")

LOG_PATH.write_text("\n".join(LOG) + "\n", encoding="utf-8")
Gui.Selection.clearSelection()
App.closeDocument(doc.Name)
print("sewing-creation-smoke=passed", flush=True)
