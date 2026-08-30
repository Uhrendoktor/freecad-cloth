"""Native Coin3D seam overlays for the FreeCAD Sewing workbench."""

class SeamViewProvider:
    """Render seam segments, direction arrows, and a persistent seam label."""
    def __init__(self, obj):
        self.Object = obj
        self.ViewObject = None

    def attach(self, vobj):
        self.ViewObject = vobj
        self._refresh()

    def claimChildren(self): return []
    def getIcon(self): return ""
    def onChanged(self, vobj, prop):
        if prop in {"Visibility", "DisplayMode"}: return
        self._refresh()
    def updateData(self, obj, prop):
        if prop in {"Shape", "Status", "ReversedB", "Label", "Diagnostic"}: self._refresh()

    def _refresh(self):
        if self.ViewObject is None: return
        try:
            from pivy import coin
            root = coin.SoSeparator()
            edges = list(self.Object.Shape.Edges)
            for index, edge in enumerate(edges[:2]):
                vertices = edge.Vertexes
                if len(vertices) < 2: continue
                p0, p1 = vertices[0].Point, vertices[-1].Point
                if index == 1 and bool(getattr(self.Object, "ReversedB", False)): p0, p1 = p1, p0
                coords = coin.SoCoordinate3()
                coords.point.setValues(0, 2, [(p0.x, p0.y, p0.z + 0.03), (p1.x, p1.y, p1.z + 0.03)])
                lines = coin.SoLineSet(); lines.numVertices = 2
                segment = coin.SoSeparator(); segment.addChild(coords); segment.addChild(lines); root.addChild(segment)
                dx, dy = p1.x-p0.x, p1.y-p0.y; length = (dx*dx+dy*dy)**0.5
                if length > 1e-9:
                    ux, uy = dx/length, dy/length; size = min(5.0, length*0.12); mx, my = (p0.x+p1.x)/2, (p0.y+p1.y)/2
                    bx, by = mx-ux*size, my-uy*size; lx, ly = bx-uy*size*0.6, by+ux*size*0.6; rx, ry = bx+uy*size*0.6, by-ux*size*0.6
                    ac = coin.SoCoordinate3(); ac.point.setValues(0, 3, [(lx,ly,p0.z+0.05),(mx,my,p0.z+0.05),(rx,ry,p0.z+0.05)])
                    al = coin.SoLineSet(); al.numVertices = 3; arrow = coin.SoSeparator(); arrow.addChild(ac); arrow.addChild(al); root.addChild(arrow)
            if edges and edges[0].Vertexes:
                a, b = edges[0].Vertexes[0].Point, edges[0].Vertexes[-1].Point
                text = coin.SoAsciiText(); text.string = str(getattr(self.Object, "SeamId", self.Object.Label)); text.justification = coin.SoAsciiText.CENTER
                text.position = ((a.x+b.x)/2, (a.y+b.y)/2, max(a.z,b.z)+0.1); root.addChild(text)
            self.ViewObject.RootNode.removeAllChildren(); self.ViewObject.RootNode.addChild(root)
        except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
            pass

    def __getstate__(self): return {}
    def __setstate__(self, state): self.ViewObject = None


def install_seam_view_providers(document):
    """Install overlays on all current seam objects; safe in headless imports."""
    try:
        import FreeCADGui
    except ImportError:
        return 0
    installed = 0
    for obj in getattr(document, "Objects", ()):
        if not getattr(obj, "SeamId", ""): continue
        try:
            obj.ViewObject.Proxy = SeamViewProvider(obj)
            installed += 1
        except (AttributeError, RuntimeError):
            pass
    return installed
