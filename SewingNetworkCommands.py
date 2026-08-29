"""FreeCAD commands for creating and editing sewing networks."""


def _selected_seams():
    import FreeCADGui as Gui
    seams = [obj for obj in Gui.Selection.getSelection() if getattr(obj, "SeamId", "")]
    if not seams:
        raise ValueError("select one or more canonical seams before creating a sewing network")
    return seams


def _selected_pattern_edges():
    from SewingCommands import _selected_pattern_edges as select_edges
    return select_edges(allow_many=False)


def create_network_from_selection():
    """Persist selected canonical seam segments as one editable M:N network."""
    import FreeCAD as App
    from SewingNetwork import add_sewing_network

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before creating a sewing network")
    seams = _selected_seams()
    groups = {str(getattr(seam, "StitchGroup", "")).strip() for seam in seams}
    if len(groups) != 1 or not next(iter(groups)):
        raise ValueError("selected seams must share one non-empty stitch group")
    relationship_id = next(iter(groups))
    existing = {str(getattr(obj, "RelationshipId", "")) for obj in doc.Objects}
    name = "SewingNetwork"
    index = 1
    while name in {obj.Name for obj in doc.Objects}:
        index += 1
        name = "SewingNetwork%d" % index
    if relationship_id in existing:
        raise ValueError("a sewing network with this relationship id already exists")
    network = add_sewing_network(doc, seams, relationship_id, name)
    doc.recompute()
    return network


def create_free_sewing_from_selection():
    """Create a 1:1 free-sewing relationship and open its range editor."""
    import FreeCAD as App
    from PatternObjects import add_seam
    from SewingNetwork import SewingMember, add_sewing_network, build_mn_seams
    from SewingNetworkGui import show_sewing_network_task
    from SewingObjects import _edge_length

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before creating free sewing")
    selected = _selected_pattern_edges()
    pieces = {str(getattr(obj, "PieceId", "")): obj for obj in doc.Objects if getattr(obj, "PatternType", "") == "PatternPiece"}
    piece_a, edge_a = selected[0]
    piece_b, edge_b = selected[1]
    relationship_id = "free-sewing-1"
    existing = {str(getattr(obj, "RelationshipId", "")) for obj in doc.Objects}
    index = 1
    while relationship_id in existing:
        index += 1
        relationship_id = "free-sewing-%d" % index
    side_a = (SewingMember(str(piece_a.PieceId), edge_a),)
    side_b = (SewingMember(str(piece_b.PieceId), edge_b),)
    lengths = {
        (side_a[0].piece_id, edge_a): _edge_length(pieces[side_a[0].piece_id], edge_a),
        (side_b[0].piece_id, edge_b): _edge_length(pieces[side_b[0].piece_id], edge_b),
    }
    models = build_mn_seams(relationship_id, side_a, side_b, lengths)
    seam_objects = [add_seam(doc, model) for model in models]
    network = add_sewing_network(doc, seam_objects, relationship_id, "SewingNetwork%d" % index)
    doc.recompute()
    show_sewing_network_task(network)
    return network


def edit_selected_network():
    import FreeCADGui as Gui
    from SewingNetworkGui import show_sewing_network_task
    network = next((obj for obj in Gui.Selection.getSelection() if getattr(obj, "SewingType", "") == "SewingNetwork"), None)
    if network is None:
        raise ValueError("select a sewing network before editing it")
    return show_sewing_network_task(network)


def _has_selected_seams():
    try:
        return bool(_selected_seams())
    except (ImportError, ValueError):
        return False


def _has_selected_pattern_edges():
    try:
        _selected_pattern_edges()
        return True
    except (ImportError, ValueError):
        return False


def _has_selected_network():
    try:
        import FreeCADGui as Gui
        return any(getattr(obj, "SewingType", "") == "SewingNetwork" for obj in Gui.Selection.getSelection())
    except ImportError:
        return False


try:
    import FreeCADGui as Gui

    class _CreateNetworkCommand:
        def Activated(self): return create_network_from_selection()
        def IsActive(self):
            try:
                import FreeCAD as App
                return App.ActiveDocument is not None and _has_selected_seams()
            except ImportError:
                return False
        def GetResources(self):
            return {"MenuText": "Create Sewing Network", "ToolTip": "Group selected canonical seam segments into an M:N sewing network"}

    class _FreeSewingCommand:
        def Activated(self): return create_free_sewing_from_selection()
        def IsActive(self):
            try:
                import FreeCAD as App
                return App.ActiveDocument is not None and _has_selected_pattern_edges()
            except ImportError:
                return False
        def GetResources(self):
            return {"MenuText": "Free Sewing", "ToolTip": "Create a partial-edge sewing relationship and edit its ranges"}

    class _EditNetworkCommand:
        def Activated(self): return edit_selected_network()
        def IsActive(self):
            try:
                import FreeCAD as App
                return App.ActiveDocument is not None and _has_selected_network()
            except ImportError:
                return False
        def GetResources(self):
            return {"MenuText": "Edit Sewing Network", "ToolTip": "Edit M:N/free-sewing edge ranges"}

    Gui.addCommand("ClothSewing_CreateNetwork", _CreateNetworkCommand())
    Gui.addCommand("ClothSewing_FreeSewing", _FreeSewingCommand())
    Gui.addCommand("ClothSewing_EditNetwork", _EditNetworkCommand())
except (ImportError, AttributeError):
    pass

COMMANDS = ["ClothSewing_CreateNetwork", "ClothSewing_FreeSewing", "ClothSewing_EditNetwork"]
