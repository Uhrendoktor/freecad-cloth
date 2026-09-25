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


def _pieces_by_id(doc):
    return {getattr(o, "PieceId", ""): o for o in doc.Objects if getattr(o, "PatternType", "") == "PatternPiece"}


def _collect_selected_pattern_edges():
    """Return all selected semantic pattern-piece edges in selection order."""
    import FreeCADGui as Gui
    edges = []
    seen = set()
    for selection in Gui.Selection.getSelectionEx():
        obj = selection.Object
        if getattr(obj, "PatternType", "") != "PatternPiece":
            continue
        for sub_name in selection.SubElementNames:
            if not str(sub_name).startswith("Edge"):
                continue
            try:
                edge_number = int(str(sub_name)[4:])
            except ValueError:
                continue
            if edge_number <= 0:
                continue
            edge = edge_number - 1
            key = (id(obj), edge)
            if key in seen:
                continue
            seen.add(key)
            edges.append((obj, edge))
    return edges


def _selected_pattern_edges(allow_many=False):
    """Return selected pattern-piece edge references after count/piece validation."""
    edges = _collect_selected_pattern_edges()
    if (not allow_many and len(edges) != 2) or (allow_many and len(edges) < 2):
        count = "at least two" if allow_many else "exactly two"
        raise ValueError("select %s edges on pattern pieces" % count)
    if len({id(obj) for obj, _edge in edges}) != 2:
        raise ValueError("a sewing relationship must connect two different pattern pieces")
    return edges


def _has_any_selected_pattern_edges():
    try:
        return bool(_collect_selected_pattern_edges())
    except (ImportError, ValueError):
        return False


_ACTIVE_STAGED_SEWING_TASK_PANEL = None
_ACTIVE_SEWING_OPERATION_TASK_PANEL = None


def get_active_staged_sewing_task_panel():
    """Return the task panel most recently opened by a public staged-sewing command."""
    return _ACTIVE_STAGED_SEWING_TASK_PANEL


def start_staged_seam_creation():
    global _ACTIVE_STAGED_SEWING_TASK_PANEL
    from freecad_cloth.sewing.SewingCreationGui import show_sewing_creation_task
    _ACTIVE_STAGED_SEWING_TASK_PANEL = show_sewing_creation_task("seam")
    return _ACTIVE_STAGED_SEWING_TASK_PANEL


def start_staged_mn_sewing_creation():
    global _ACTIVE_STAGED_SEWING_TASK_PANEL
    from freecad_cloth.sewing.SewingCreationGui import show_sewing_creation_task
    _ACTIVE_STAGED_SEWING_TASK_PANEL = show_sewing_creation_task("mn")
    return _ACTIVE_STAGED_SEWING_TASK_PANEL


def start_staged_free_sewing_creation():
    global _ACTIVE_STAGED_SEWING_TASK_PANEL
    from freecad_cloth.sewing.SewingCreationGui import show_sewing_creation_task
    _ACTIVE_STAGED_SEWING_TASK_PANEL = show_sewing_creation_task("free")
    return _ACTIVE_STAGED_SEWING_TASK_PANEL


def _has_two_selected_pattern_edges():
    try:
        _selected_pattern_edges()
        return True
    except (ImportError, ValueError):
        return False


def _has_mn_selection():
    try:
        _selected_pattern_edges(allow_many=True)
        return True
    except (ImportError, ValueError):
        return False


def create_seam_from_selection():
    """Create a persistent canonical seam from two selected pattern edges."""
    import FreeCAD as App
    from freecad_cloth.pattern.PatternModel import Seam
    from freecad_cloth.pattern.PatternObjects import add_seam
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before creating a seam")
    (piece_a, edge_a), (piece_b, edge_b) = _selected_pattern_edges()
    existing_ids = {str(getattr(seam, "SeamId", "")) for seam in _seams(doc)}
    index = len(existing_ids) + 1
    prefix = "seam-%d" % index
    while prefix in existing_ids:
        index += 1
        prefix = "seam-%d" % index
    seam_model = Seam(str(piece_a.PieceId), edge_a, str(piece_b.PieceId), edge_b, id=prefix)
    seam = add_seam(doc, seam_model)
    doc.recompute()
    return seam


def create_mn_sewing_from_selection():
    """Create a persistent 1:N, M:1, or M:N sewing network."""
    import FreeCAD as App
    from freecad_cloth.pattern.PatternObjects import add_seam
    from freecad_cloth.sewing.SewingNetwork import SewingMember, add_sewing_network, build_mn_seams
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before creating sewing")
    selected = _selected_pattern_edges(allow_many=True)
    pieces = _pieces_by_id(doc)
    piece_ids = []
    for piece, _edge in selected:
        pid = str(piece.PieceId)
        if pid not in piece_ids:
            piece_ids.append(pid)
    if len(piece_ids) != 2:
        raise ValueError("select edges from exactly two pattern pieces")
    first_piece = piece_ids[0]
    side_a = tuple(SewingMember(first_piece, edge) for piece, edge in selected if str(piece.PieceId) == first_piece)
    side_b = tuple(SewingMember(piece_ids[1], edge) for piece, edge in selected if str(piece.PieceId) == piece_ids[1])
    lengths = {}
    from freecad_cloth.sewing.SewingObjects import _edge_length
    for member in side_a + side_b:
        lengths[(member.piece_id, member.edge)] = _edge_length(pieces[member.piece_id], member.edge)
    existing_ids = {str(getattr(obj, "RelationshipId", "")) for obj in doc.Objects if getattr(obj, "SewingType", "") == "SewingNetwork"}
    index = len(existing_ids) + 1
    relationship_id = "sewing-%d" % index
    while relationship_id in existing_ids:
        index += 1
        relationship_id = "sewing-%d" % index
    models = build_mn_seams(relationship_id, side_a, side_b, lengths)
    seam_objects = [add_seam(doc, model) for model in models]
    network = add_sewing_network(doc, seam_objects, relationship_id, "SewingNetwork%d" % index)
    doc.recompute()
    return network


def create_sewing_operation():
    import FreeCAD as App
    from freecad_cloth.sewing.SewingObjects import add_sewing_operation
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    seam = _selected_seam(doc)
    pieces = _pieces_by_id(doc)
    try:
        a, b = pieces[str(seam.PieceA)], pieces[str(seam.PieceB)]
    except KeyError:
        raise ValueError("the seam references pattern pieces that are not in the active document")
    n = len([o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingOperation"]) + 1
    obj = add_sewing_operation(doc, seam, a, b, "SewingOperation%d" % n)
    doc.recompute()
    return obj


def get_active_sewing_operation_task_panel():
    """Return the task panel most recently opened by the public sewing-operation command."""
    return _ACTIVE_SEWING_OPERATION_TASK_PANEL


def edit_sewing_operation():
    global _ACTIVE_SEWING_OPERATION_TASK_PANEL
    import FreeCADGui as Gui
    obj = next((o for o in Gui.Selection.getSelection() if getattr(o, "SewingType", "") == "SewingOperation"), None)
    if obj is None:
        raise ValueError("select a sewing operation before editing it")
    from freecad_cloth.sewing.SewingGui import show_sewing_task
    _ACTIVE_SEWING_OPERATION_TASK_PANEL = show_sewing_task(obj)
    return _ACTIVE_SEWING_OPERATION_TASK_PANEL


def reverse_selected_seam():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing seam orientation")
    seam = _selected_seam(doc)
    seam.ReversedB = not bool(seam.ReversedB)
    doc.recompute()
    return seam


def toggle_selected_alignment():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing seam alignment")
    seam = _selected_seam(doc)
    seam.Alignment = "uniform" if str(seam.Alignment) == "endpoints" else "endpoints"
    doc.recompute()
    return seam


def validate_seams():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        return []
    ops = [o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingOperation"]
    networks = [o for o in doc.Objects if getattr(o, "SewingType", "") == "SewingNetwork"]
    for obj in ops + networks:
        obj.Proxy.execute(obj)
    doc.recompute()
    return ([(o.Name, o.Status, float(o.LengthDifference)) for o in ops] +
            [(o.Name, o.Status, float(o.LengthDifference)) for o in networks])


def repair_selected_seam():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before repairing a seam")
    seam = _selected_seam(doc)
    from freecad_cloth.sewing.SewingGui import correspondence_report, repair_correspondence_settings
    length_a = float(getattr(seam, "LengthA", 0.0))
    length_b = float(getattr(seam, "LengthB", 0.0))
    if length_a <= 0.0 or length_b <= 0.0:
        pieces = _pieces_by_id(doc)
        try:
            from freecad_cloth.sewing.SewingObjects import _edge_length
            length_a = _edge_length(pieces[str(seam.PieceA)], int(seam.EdgeA))
            length_b = _edge_length(pieces[str(seam.PieceB)], int(seam.EdgeB))
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            raise ValueError("cannot determine seam lengths for repair: %s" % exc) from exc
    # Refresh only the existing semantic edge IDs. Never use a changed ordinal
    # to retarget a seam to another edge; topology repair is an explicit operation.
    pieces = _pieces_by_id(doc)
    refreshed = []
    try:
        from freecad_cloth.pattern.PatternObjects import _edge_records, refresh_edge_reference_signature
        for side, edge_attr, piece_attr, id_attr, sig_attr in (
            ("A", "EdgeA", "PieceA", "EdgeAId", "EdgeASignature"),
            ("B", "EdgeB", "PieceB", "EdgeBId", "EdgeBSignature"),
        ):
            piece_id = str(getattr(seam, piece_attr, ""))
            piece = pieces.get(piece_id)
            if piece is None:
                raise ValueError("cannot repair seam %s: pattern piece %s is missing" % (side, piece_id))
            edge_id = str(getattr(seam, id_attr, "")).strip()
            if not edge_id:
                raise ValueError("cannot repair seam %s: semantic edge ID is missing" % side)
            signature = refresh_edge_reference_signature(piece, edge_id)
            record = next(
                (item for item in _edge_records(piece) if str(item.get("id")) == edge_id),
                None,
            )
            if record is None:
                raise ValueError("cannot repair seam %s: semantic edge ID disappeared" % side)
            refreshed.append((edge_attr, sig_attr, int(record["ordinal"]), signature))
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as exc:
        raise ValueError("cannot refresh stale seam edge references: %s" % exc) from exc
    for edge_attr, sig_attr, edge_index, signature in refreshed:
        setattr(seam, edge_attr, edge_index)
        setattr(seam, sig_attr, signature)

    report = correspondence_report(seam, length_a, length_b, 0.05)
    message = repair_correspondence_settings(seam, report)
    doc.recompute()
    return message


def focus_selected_seam_3d():
    """Fit the 3D viewport to the selected semantic seam."""
    import FreeCAD as App
    import FreeCADGui as Gui
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before focusing a seam")
    seam = _selected_seam(doc)
    from freecad_cloth.sewing.SewingView import apply_seam_colors
    apply_seam_colors(doc.Objects)
    if getattr(seam, "Shape", None) is None or seam.Shape.isNull():
        raise ValueError("selected seam has no presentation geometry")
    previous = []
    for obj in doc.Objects:
        view = getattr(obj, "ViewObject", None)
        if view is None:
            continue
        previous.append((obj, bool(getattr(view, "Visibility", True))))
        view.Visibility = obj is seam
    try:
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(seam)
        view = Gui.activeDocument().activeView()
        view.viewAxonometric()
        view.fitAll()
        doc.recompute()
    finally:
        for obj, visible in previous:
            try:
                obj.ViewObject.Visibility = visible
            except (AttributeError, RuntimeError):
                pass
    return seam


def _edit_selected_seam_side(side):
    import FreeCAD as App
    import FreeCADGui as Gui
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before editing a seam")
    seam = _selected_seam(doc)
    side = str(side).upper()
    if side not in {"A", "B"}:
        raise ValueError("seam side must be A or B")
    piece = getattr(seam, "PatternA" if side == "A" else "PatternB", None)
    semantic_id = str(getattr(seam, "EdgeAId" if side == "A" else "EdgeBId", "")).strip()
    sketch = getattr(piece, "Sketch", None) if piece is not None else None
    if sketch is None or not semantic_id:
        raise ValueError("selected seam side %s has no native Sketcher source" % side)
    semantic_ids = tuple(str(value) for value in (getattr(sketch, "SemanticEdgeIds", ()) or ()))
    try:
        edge_index = semantic_ids.index(semantic_id)
    except ValueError as exc:
        raise ValueError("seam side %s is not present in the Sketcher semantic edge map" % side) from exc
    focus_selected_seam_3d()
    if Gui.activeDocument().getInEdit():
        Gui.activeDocument().resetEdit()
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(piece)
    Gui.activeDocument().setEdit(sketch.Name)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(sketch, "Edge%d" % (edge_index + 1))
    return sketch, edge_index


def edit_selected_seam_side_a():
    return _edit_selected_seam_side("A")


def edit_selected_seam_side_b():
    return _edit_selected_seam_side("B")


def show_sewing_2d():
    import FreeCADGui as Gui
    if not Gui.activeDocument():
        return
    from freecad_cloth.sewing.SewingView import apply_seam_colors
    document = Gui.activeDocument().Document
    apply_seam_colors(document.Objects)
    Gui.Selection.clearSelection()
    view = Gui.activeDocument().activeView()
    view.viewTop()
    view.fitAll()


COMMANDS = [
    "ClothSewing_CreateSeam", "ClothSewing_CreateMNSewing", "ClothSewing_CreateOperation",
    "ClothSewing_EditOperation", "ClothSewing_ReverseSeam", "ClothSewing_ToggleAlignment",
    "ClothSewing_Validate", "ClothSewing_RepairSeam", "ClothSewing_FocusSeam3D",
    "ClothSewing_EditSeamSideA", "ClothSewing_EditSeamSideB", "ClothSewing_Show2D",
]
_COMMAND_HANDLERS = {
    "ClothSewing_CreateSeam": start_staged_seam_creation,
    "ClothSewing_CreateMNSewing": start_staged_mn_sewing_creation,
    "ClothSewing_CreateOperation": create_sewing_operation,
    "ClothSewing_EditOperation": edit_sewing_operation,
    "ClothSewing_ReverseSeam": reverse_selected_seam,
    "ClothSewing_ToggleAlignment": toggle_selected_alignment,
    "ClothSewing_Validate": validate_seams,
    "ClothSewing_RepairSeam": repair_selected_seam,
    "ClothSewing_FocusSeam3D": focus_selected_seam_3d,
    "ClothSewing_EditSeamSideA": edit_selected_seam_side_a,
    "ClothSewing_EditSeamSideB": edit_selected_seam_side_b,
    "ClothSewing_Show2D": show_sewing_2d,
}
_MENU_TEXT = {
    "ClothSewing_CreateSeam": "Create Seam",
    "ClothSewing_CreateMNSewing": "Create M:N Sewing",
    "ClothSewing_CreateOperation": "Create Sewing Operation",
    "ClothSewing_EditOperation": "Edit Sewing Operation",
    "ClothSewing_ReverseSeam": "Reverse Seam",
    "ClothSewing_ToggleAlignment": "Toggle Seam Alignment",
    "ClothSewing_Validate": "Validate Sewing",
    "ClothSewing_RepairSeam": "Repair Seam",
    "ClothSewing_FocusSeam3D": "Focus Seam in 3D",
    "ClothSewing_EditSeamSideA": "Edit Seam Side A in Sketcher",
    "ClothSewing_EditSeamSideB": "Edit Seam Side B in Sketcher",
    "ClothSewing_Show2D": "Show Sewing 2D",
}
_TOOLTIPS = {
    "ClothSewing_CreateSeam": "Preview, validate, and commit a seam from two selected pattern edges",
    "ClothSewing_CreateMNSewing": "Preview, validate, and commit a deterministic 1:N, M:1, or M:N sewing relationship",
    "ClothSewing_CreateOperation": "Create a sewing operation from the selected seam",
    "ClothSewing_EditOperation": "Edit seam alignment, orientation, tolerance, and stitch samples",
    "ClothSewing_ReverseSeam": "Reverse the B-side stitch correspondence",
    "ClothSewing_ToggleAlignment": "Toggle endpoint and uniform seam correspondence",
    "ClothSewing_Validate": "Validate sewing operations and report seam length mismatches",
    "ClothSewing_RepairSeam": "Repair reversible or invalid-range seam correspondence without hiding length mismatch",
    "ClothSewing_FocusSeam3D": "Show the selected semantic seam in 3D and fit the view to it",
    "ClothSewing_EditSeamSideA": "Open the seam A edge in its authoritative native Sketcher source",
    "ClothSewing_EditSeamSideB": "Open the seam B edge in its authoritative native Sketcher source",
    "ClothSewing_Show2D": "Show pattern, seam, and stitch correspondence in top view",
}
def _has_active_document():
    try:
        import FreeCAD as App
        return App.ActiveDocument is not None
    except ImportError:
        return False

def _has_selected_seam():
    try:
        import FreeCADGui as Gui
        return any(getattr(o, "SeamId", "") for o in Gui.Selection.getSelection())
    except ImportError:
        return False

def _has_selected_operation():
    try:
        import FreeCADGui as Gui
        return any(getattr(o, "SewingType", "") == "SewingOperation" for o in Gui.Selection.getSelection())
    except ImportError:
        return False
class _SewingCommand:
    def __init__(self, function, active, tooltip, menu_text=None, pixmap=None):
        self.function, self.active, self.tooltip = function, active, tooltip
        self.menu_text = menu_text or function.__name__.replace("_", " ").title()
        self.pixmap = pixmap
    def Activated(self): return self.function()
    def IsActive(self): return bool(self.active())
    def GetResources(self):
        resources = {"MenuText": self.menu_text, "ToolTip": self.tooltip}
        if self.pixmap:
            resources["Pixmap"] = self.pixmap
        return resources

_ACTIVATION = {
    "ClothSewing_CreateSeam": lambda: _has_active_document() and _has_any_selected_pattern_edges(),
    "ClothSewing_CreateMNSewing": lambda: _has_active_document() and _has_any_selected_pattern_edges(),
    "ClothSewing_CreateOperation": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_EditOperation": lambda: _has_active_document() and _has_selected_operation(),
    "ClothSewing_ReverseSeam": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_ToggleAlignment": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_Validate": lambda: _has_active_document(),
    "ClothSewing_RepairSeam": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_FocusSeam3D": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_EditSeamSideA": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_EditSeamSideB": lambda: _has_active_document() and _has_selected_seam(),
    "ClothSewing_Show2D": lambda: _has_active_document(),
}

try:
    import FreeCADGui as Gui
    for name, function in _COMMAND_HANDLERS.items():
        icon_path = _ICON_DIR / (name + ".svg")
        if not icon_path.is_file() and name == "ClothSewing_RepairSeam":
            icon_path = _ICON_DIR / "ClothSewing_Validate.svg"
        Gui.addCommand(name, _SewingCommand(function, _ACTIVATION[name], _TOOLTIPS[name], _MENU_TEXT[name], str(icon_path)))
except (ImportError, AttributeError):
    pass
