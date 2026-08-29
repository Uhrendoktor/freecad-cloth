"""FreeCAD commands for grouping canonical seams into sewing networks."""


def _selected_seams():
    import FreeCADGui as Gui

    seams = [obj for obj in Gui.Selection.getSelection() if getattr(obj, "SeamId", "")]
    if not seams:
        raise ValueError("select one or more canonical seams before creating a sewing network")
    return seams


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


def _has_selected_seams():
    try:
        return bool(_selected_seams())
    except (ImportError, ValueError):
        return False


COMMANDS = ["ClothSewing_CreateNetwork"]


try:
    import FreeCADGui as Gui

    class _CreateNetworkCommand:
        def Activated(self):
            return create_network_from_selection()

        def IsActive(self):
            try:
                import FreeCAD as App
                return App.ActiveDocument is not None and _has_selected_seams()
            except ImportError:
                return False

        def GetResources(self):
            return {
                "MenuText": "Create Sewing Network",
                "ToolTip": "Group selected canonical seam segments into an M:N sewing network",
            }

    Gui.addCommand("ClothSewing_CreateNetwork", _CreateNetworkCommand())
except (ImportError, AttributeError):
    pass
