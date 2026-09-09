"""Commands for the Cloth Sewing workbench."""
from pathlib import Path


_ICON_DIR = Path(__file__).resolve().parents[2] / "resources" / "icons"


def _seams(doc):
    return [o for o in doc.Objects if getattr(o, "SeamId", "")]


def _selected_seam(doc):
    import FreeCADGui as Gui
    for obj in Gui.Selection.getSelection():
        if getattr(obj, "SeamId", ""):
            return obj
    seams = _seams(doc)
    if seams:
        return seams[0]
    raise ValueError("create or select a seam before creating a sewing operation")
