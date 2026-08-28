"""Native FreeCAD feature for editable sewing-pattern pieces.

The data/model layer remains FreeCAD-independent; this module is only the
presentation bridge used when FreeCAD is available.
"""
import json

from PatternGeometry import rectangle


def _points(outline):
    import FreeCAD as App
    return [App.Vector(float(x), float(y), 0.0) for x, y in outline]


class PatternPieceFeature:
    """FeaturePython proxy that rebuilds a planar pattern face on recompute."""

    def __init__(self, obj):
        self.Object = obj
        obj.Proxy = self

    def execute(self, obj):
        import Part

        try:
            outline = json.loads(obj.OutlineJSON)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("OutlineJSON must contain a JSON point list") from exc
        points = [(float(p[0]), float(p[1])) for p in outline]
        if len(points) < 3:
            raise ValueError("pattern outline needs at least three points")

        vectors = _points(points)
        vectors.append(vectors[0])
        obj.Shape = Part.Face(Part.makePolygon(vectors))
        obj.Label = obj.PieceId or obj.Name

    def onChanged(self, obj, prop):
        if prop in {"Width", "Height"} and obj.DraftKind == "Rectangle":
            geometry = rectangle(float(obj.Width), float(obj.Height))
            obj.OutlineJSON = json.dumps(geometry.sampled_outline(), separators=(",", ":"))


def add_pattern_feature(doc, name="PatternPiece", width=100.0, height=60.0):
    """Create an editable rectangular pattern piece in *doc*."""
    geometry = rectangle(width, height)
    obj = doc.addObject("Part::FeaturePython", name)
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyString", "PieceId", "Cloth").PieceId = name
    obj.addProperty("App::PropertyEnumeration", "DraftKind", "Cloth")
    obj.DraftKind = ["Rectangle", "Custom"]
    obj.DraftKind = "Rectangle"
    obj.addProperty("App::PropertyLength", "Width", "Dimensions").Width = width
    obj.addProperty("App::PropertyLength", "Height", "Dimensions").Height = height
    obj.addProperty("App::PropertyLength", "SeamAllowance", "Cloth").SeamAllowance = 0.0
    obj.addProperty("App::PropertyAngle", "GrainlineAngle", "Cloth").GrainlineAngle = 0.0
    obj.addProperty("App::PropertyString", "OutlineJSON", "Geometry")
    obj.OutlineJSON = json.dumps(geometry.sampled_outline(), separators=(",", ":"))
    PatternPieceFeature(obj)
    obj.recompute()
    return obj
