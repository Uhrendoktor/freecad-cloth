"""Native Coin3D seam overlay with direction arrows and labels."""
from math import atan2, cos, sin


def pattern_pieces_for_2d(objects):
    return [obj for obj in objects if getattr(obj, "PatternType", "") == "PatternPiece"]


class SeamViewProvider:
    """Render a seam as two highlighted segments with direction arrows and label."""
    def __init__(self, obj):
        self.Object = obj
        self._root = None
        self._build()

    def getIcon(self):
        return ""

    def attach(self, vobj):
        self.ViewObject = vobj
        self._build()

    def claimChildren(self):
        return []

    def onChanged(self, vobj, prop):
        if prop in {"Visibility", "DisplayMode"}:
            return
        self._build()

    def updateData(self, obj, prop):
        if prop in {"Shape", "Status", "ReversedB", "Label", "Diagnostic"}:
            self._build()

    def _build(self):
        try:
            from pivy import coin
            import FreeCAD as App
        except ImportError:
            return
        if not hasattr(self, "ViewObject"):
            return
        root = coin.SoSeparator()
        seam = self.Object
        status = str(getattr(seam, "Status", "Valid"))
        # Use the already-resolved seam Shape endpoints so visualization follows
        # native pattern placement without maintaining a second geometry model.
        try:
            edges = list(seam.Shape.Edges)
            for edge_index, edge in enumerate(edges[:2]):
                vertices = edge.Vertexes
                if len(vertices) < 2:
                    continue
                p0, p1 = vertices[0].Point, vertices[-1].Point
                line = coin.SoSeparator()
                coords = coin.SoCoordinate3(); coords.point.setValues(0, 2, [(p0.x, p0.y, p0.z + 0.02), (p1.x, p1.y, p1.z + 0.02)])
                line.addChild(coords)
                line_set = coin.SoLineSet(); line_set.numVertices = 2; line.addChild(line_set)
                root.addChild(line)
                # Small V-shaped arrowhead at the segment midpoint indicates
                # sewing direction. The B side is reversed by reversing p0/p1.
                if edge_index == 1 and bool(getattr(seam, "ReversedB", False)):
                    p0, p1 = p1, p0
                dx, dy = p1.x - p0.x, p1.y - p0.y
                norm = (dx * dx + dy * dy) ** 0.5
                if norm > 1e-9:
                    mx, my = (p0.x + p1.x) * 0.5, (p0.y + p1.y) * 0.5
                    ux, uy = dx / norm, dy / norm
                    size = min(5.0, norm * 0.12)
                    bx, by = mx - ux * size, my - uy * size
                    lx, ly = bx - uy * size * 0.6, by + ux * size * 0.6
                    rx, ry = bx + uy * size * 0.6, by - ux * size * 0.6
                    ac = coin.SoCoordinate3(); ac.point.setValues(0, 3, [(lx, ly, p0.z + 0.04), (mx, my, p0.z + 0.04), (rx, ry, p0.z + 0.04)])
                    als = coin.SoLineSet(); als.numVertices = 3
                    arr = coin.SoSeparator(); arr.addChild(ac); arr.addChild(als); root.addChild(arr)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        try:
            edges = list(seam.Shape.Edges)
            if edges:
                p0, p1 = edges[0].Vertexes[0].Point, edges[0].Vertexes[-1].Point
                text = coin.SoAsciiText(); text.string = str(getattr(seam, "SeamId", seam.Label))
                text.justification = coin.SoAsciiText.CENTER
                text.position = App.Vector((p0.x + p1.x) * 0.5, (p0.y + p1.y) * 0.5, max(p0.z, p1.z) + 0.08)
                root.addChild(text)
        except (AttributeError, RuntimeError, TypeError):
            pass
        try:
            self.ViewObject.RootNode.removeAllChildren()
            self.ViewObject.RootNode.addChild(root)
        except (AttributeError, RuntimeError):
            self._root = root

    def __getstate__(self):
        return {}

    def __setstate__(self, state):
        self._root = None
