"""Small, FreeCAD-native contract for authoritative Cloth Sketcher objects.

The contract deliberately does not mirror geometry or constraints into Cloth.
It only maintains stable semantic IDs alongside Sketcher geometry so the
solver/sewing adapters can reject topology loss instead of silently retargeting.
"""

CONTRACT_VERSION = "1"
AUTHORITY = "Sketcher"


def ensure_semantic_edge_ids(sketch, piece_id):
    """Validate/extend the geometry-aligned semantic ID list.

    Appended Sketcher geometry is assigned a new deterministic ID. A shrink in
    geometry cardinality is rejected because we cannot know whether a deleted
    element was a boundary edge or construction/reference geometry; this keeps
    seams fail-closed instead of retargeting them by ordinal.
    """
    geometry = tuple(getattr(sketch, "Geometry", ()) or ())
    ids = [str(value) for value in (getattr(sketch, "SemanticEdgeIds", ()) or ())]
    if len(ids) > len(geometry):
        raise ValueError(
            "Sketcher topology changed by deletion; semantic edge mapping must be repaired explicitly"
        )
    while len(ids) < len(geometry):
        ids.append(f"{piece_id}:edge:{len(ids)}")
    if len(ids) != len(set(ids)):
        raise ValueError("Sketcher semantic edge IDs must be unique")
    if hasattr(sketch, "SemanticEdgeIds"):
        sketch.SemanticEdgeIds = ids
    return tuple(ids)


def configure_authority(sketch, piece_id):
    """Install persistent metadata without taking ownership of Sketcher data."""
    if "PatternPieceId" not in sketch.PropertiesList:
        sketch.addProperty("App::PropertyString", "PatternPieceId", "Cloth Pattern")
    sketch.PatternPieceId = str(piece_id)
    if "SemanticEdgeIds" not in sketch.PropertiesList:
        sketch.addProperty("App::PropertyStringList", "SemanticEdgeIds", "Cloth Pattern")
    if "GeometryAuthority" not in sketch.PropertiesList:
        sketch.addProperty("App::PropertyString", "GeometryAuthority", "Cloth Pattern")
    sketch.GeometryAuthority = AUTHORITY
    if "GeometryContractVersion" not in sketch.PropertiesList:
        sketch.addProperty("App::PropertyString", "GeometryContractVersion", "Cloth Pattern")
    sketch.GeometryContractVersion = CONTRACT_VERSION
    if "GeometrySource" not in sketch.PropertiesList:
        sketch.addProperty("App::PropertyString", "GeometrySource", "Cloth Pattern")
    sketch.GeometrySource = "ClothPattern.PatternPiece"
    ensure_semantic_edge_ids(sketch, piece_id)
    return sketch
