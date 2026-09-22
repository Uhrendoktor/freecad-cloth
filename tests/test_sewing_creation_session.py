import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freecad_cloth.sewing.SewingCreationGui import SewingCreationSession


class _Selection:
    def __init__(self, selected=()):
        self.selected = list(selected)

    def getSelection(self):
        return list(self.selected)

    def clearSelection(self):
        self.selected = []

    def addSelection(self, obj):
        self.selected.append(obj)


class _Document:
    def __init__(self):
        self.Objects = []
        self.calls = []
        self._snapshot = None

    def openTransaction(self, name):
        self.calls.append(("open", name))
        self._snapshot = list(self.Objects)

    def commitTransaction(self):
        self.calls.append(("commit",))
        self._snapshot = None

    def abortTransaction(self):
        self.calls.append(("abort",))
        if self._snapshot is not None:
            self.Objects = list(self._snapshot)
        self._snapshot = None

    def recompute(self):
        self.calls.append(("recompute",))


def _builder(doc, name="Seam", status="Valid"):
    def build():
        doc.Objects.append(SimpleNamespace(Name=name, SeamId="s1", Status=status))

    return build


class SewingCreationSessionContractTests(unittest.TestCase):
    def test_preview_commit_cancel_and_failed_preview_share_one_transaction_contract(self):
        doc = _Document()
        anchor = SimpleNamespace(Name="PatternPiece")
        gui = SimpleNamespace(Selection=_Selection([anchor]))

        session = SewingCreationSession(doc, gui, "Create Seam", _builder(doc))
        preview = session.preview()
        self.assertEqual(len(preview), 1)
        self.assertEqual(doc.Objects[0].Status, "Valid")
        self.assertEqual(gui.Selection.selected, preview)
        session.commit()
        self.assertEqual([call[0] for call in doc.calls], ["open", "recompute", "recompute", "commit"])
        self.assertEqual(len(doc.Objects), 1)

        doc_cancel = _Document()
        gui_cancel = SimpleNamespace(Selection=_Selection([anchor]))
        session_cancel = SewingCreationSession(doc_cancel, gui_cancel, "Create Seam", _builder(doc_cancel))
        session_cancel.preview()
        self.assertEqual(len(doc_cancel.Objects), 1)
        session_cancel.cancel()
        self.assertEqual(doc_cancel.Objects, [])
        self.assertEqual(gui_cancel.Selection.selected, [anchor])
        self.assertIn(("abort",), doc_cancel.calls)

        doc_invalid = _Document()
        gui_invalid = SimpleNamespace(Selection=_Selection([anchor]))
        invalid = SewingCreationSession(
            doc_invalid,
            gui_invalid,
            "Create M:N Sewing",
            _builder(doc_invalid, name="SewingNetwork1", status="Length mismatch"),
        )
        with self.assertRaisesRegex(ValueError, r"Preview validation failed.*Length mismatch"):
            invalid.preview()
        self.assertEqual(doc_invalid.Objects, [])
        self.assertEqual(invalid.previewed, False)
        invalid.cancel()

    def test_preview_error_feedback_is_actionable_and_disables_commit(self):
        from freecad_cloth.sewing.SewingCreationGui import SewingCreationTaskPanel

        class _Label:
            def __init__(self):
                self.text = ""
                self.style = ""

            def setText(self, value):
                self.text = value

            def setStyleSheet(self, value):
                self.style = value

        class _Button:
            def __init__(self):
                self.enabled = True

            def setEnabled(self, value):
                self.enabled = value

        panel = SewingCreationTaskPanel.__new__(SewingCreationTaskPanel)
        panel.feedback = _Label()
        panel.commit_button = _Button()
        panel._show_error(ValueError("select exactly two edges on pattern pieces"))
        self.assertIn("Preview rejected", panel.feedback.text)
        self.assertIn("Adjust the selection", panel.feedback.text)
        self.assertFalse(panel.commit_button.enabled)


if __name__ == "__main__":
    unittest.main()
