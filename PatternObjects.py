"""FreeCAD document objects for the cloth pattern model."""
from PatternModel import PatternPiece, Seam


def add_pattern_piece(doc, piece: PatternPiece):
    """Create a lightweight App::FeaturePython object when FreeCAD is present."""
    piece.validate()
    obj = doc.addObject("App::FeaturePython", piece.name)
    obj.Label = piece.name
    obj.addProperty("App::PropertyString", "PatternType", "Cloth").PatternType = "PatternPiece"
    obj.addProperty("App::PropertyLength", "SeamAllowance", "Cloth").SeamAllowance = piece.seam_allowance
    obj.addProperty("App::PropertyAngle", "GrainlineAngle", "Cloth").GrainlineAngle = piece.grainline_angle
    obj.addProperty("App::PropertyString", "OutlineJSON", "Cloth").OutlineJSON = repr(piece.outline)
    return obj


def add_seam(doc, seam: Seam):
    seam.validate()
    obj = doc.addObject("App::FeaturePython", "Seam")
    obj.Label = f"{seam.piece_a}:{seam.edge_a} ↔ {seam.piece_b}:{seam.edge_b}"
    obj.addProperty("App::PropertyString", "PieceA", "Seam").PieceA = seam.piece_a
    obj.addProperty("App::PropertyInteger", "EdgeA", "Seam").EdgeA = seam.edge_a
    obj.addProperty("App::PropertyString", "PieceB", "Seam").PieceB = seam.piece_b
    obj.addProperty("App::PropertyInteger", "EdgeB", "Seam").EdgeB = seam.edge_b
    return obj
