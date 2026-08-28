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


def add_pattern_mesh(doc, mesh, name="ClothMesh"):
    """Create a native FreeCAD Mesh::Feature from a solver-neutral mesh."""
    import Mesh
    import FreeCAD as App
    native = Mesh.Mesh()
    for a, b, c in mesh.triangles:
        native.addFacet(
            App.Vector(mesh.vertices[a][0], mesh.vertices[a][1], 0.0),
            App.Vector(mesh.vertices[b][0], mesh.vertices[b][1], 0.0),
            App.Vector(mesh.vertices[c][0], mesh.vertices[c][1], 0.0),
        )
    obj = doc.addObject("Mesh::Feature", name)
    obj.Label = name
    obj.Mesh = native
    obj.addProperty("App::PropertyString", "ClothMeshType", "Cloth").ClothMeshType = "PatternSurface"
    obj.addProperty("App::PropertyInteger", "VertexCount", "Cloth").VertexCount = len(mesh.vertices)
    obj.addProperty("App::PropertyInteger", "TriangleCount", "Cloth").TriangleCount = len(mesh.triangles)
    return obj
