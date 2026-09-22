"""Regression tests for Pattern/Sewing -> Simulation source invalidation."""

from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR, PieceIR
from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature
import freecad_cloth.simulation.SimulationObjects as SimulationObjects


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class _Rotation:
    def __init__(self, angle=0.0):
        self.Angle = angle
        self.Axis = _Vec(0.0, 0.0, 1.0)


class _Placement:
    def __init__(self, x=0.0, y=0.0, z=0.0, angle=0.0):
        self.Base = _Vec(x, y, z)
        self.Rotation = _Rotation(angle)


class _Piece:
    PatternType = "PatternPiece"

    def __init__(self, name, piece_id, outline="[(0, 0), (100, 0), (100, 60), (0, 60)]"):
        self.Name = name
        self.PieceId = piece_id
        self.SewingOutline = outline
        self.DraftingBoundary = outline
        self.Placement = _Placement()


class _Seam:
    SeamId = "seam-1"
    PieceA = "piece-a"
    EdgeA = 0
    StartA = 0.0
    EndA = 1.0
    PieceB = "piece-b"
    EdgeB = 0
    StartB = 0.0
    EndB = 1.0
    ReversedB = False


class _Avatar:
    Name = "AvatarCollision"
    SourceObject = type("_Source", (), {"Name": "Humanoid"})()
    CollisionDeflection = 1.0
    CollisionThickness = 2.0


class _Scene:
    StitchSamples = 8
    AvatarProxy = _Avatar()

    def __init__(self, objects):
        self.Document = type("_Doc", (), {"Objects": objects})()



def _test_pattern_ir(piece_id="piece-a", x_offset=0.0):
    return PatternIR(
        (
            PieceIR(
                piece_id,
                "Pattern IR Piece",
                (
                    BoundaryIR("edge:0", "line", ((x_offset + 0.0, 0.0, 0.0), (x_offset + 100.0, 0.0, 0.0))),
                    BoundaryIR("edge:1", "line", ((x_offset + 100.0, 0.0, 0.0), (x_offset + 100.0, 60.0, 0.0))),
                    BoundaryIR("edge:2", "line", ((x_offset + 100.0, 60.0, 0.0), (x_offset + 0.0, 60.0, 0.0))),
                    BoundaryIR("edge:3", "line", ((x_offset + 0.0, 60.0, 0.0), (x_offset + 0.0, 0.0, 0.0))),
                ),
            ),
        )
    )


def test_simulation_signature_uses_compiled_pattern_ir_not_legacy_outlines():
    piece = _Piece("A", "piece-a")
    scene = _Scene([])
    pattern_ir = _test_pattern_ir()
    calls = []

    original = SimulationObjects.compile_pattern_ir
    SimulationObjects.compile_pattern_ir = lambda doc, pieces: (calls.append(tuple(pieces)) or pattern_ir)
    try:
        baseline = _simulation_source_signature(scene, [piece])
        piece.SewingOutline = "invalid legacy outline"
        piece.DraftingBoundary = "another invalid legacy outline"
        assert _simulation_source_signature(scene, [piece]) == baseline
    finally:
        SimulationObjects.compile_pattern_ir = original

    assert calls == [(piece,), (piece,)]


def test_simulation_signature_fails_closed_on_invalid_pattern_ir():
    piece = _Piece("A", "piece-a")
    scene = _Scene([])
    invalid_ir = PatternIR((PieceIR("piece-a", "invalid", ()),), ())
    original = SimulationObjects.compile_pattern_ir
    SimulationObjects.compile_pattern_ir = lambda doc, pieces: invalid_ir
    try:
        try:
            _simulation_source_signature(scene, [piece])
        except ValueError as exc:
            assert "piece needs at least one boundary" in str(exc)
        else:
            raise AssertionError("invalid PatternIR reached the simulation signature")
    finally:
        SimulationObjects.compile_pattern_ir = original


def test_simulation_document_adapter_fails_closed_on_missing_semantic_seam_edge():
    from freecad_cloth.common.PatternIRDocumentAdapter import compile_pattern_ir

    piece_a = _Piece("A", "piece-a")
    piece_b = _Piece("B", "piece-b")
    seam = _Seam()
    seam.EdgeAId = "missing-edge"
    scene = _Scene([seam])
    try:
        compile_pattern_ir(scene.Document, [piece_a, piece_b])
    except ValueError as exc:
        assert "missing semantic edge" in str(exc)
        return
    raise AssertionError("simulation accepted a seam with a missing semantic edge")

def test_signature_changes_when_piece_geometry_or_placement_changes():
    piece = _Piece("A", "piece-a")
    scene = _Scene([])
    baseline = _simulation_source_signature(scene, [piece])

    piece.Placement = _Placement(x=25.0, y=-10.0, angle=15.0)
    assert _simulation_source_signature(scene, [piece]) != baseline

    moved = _simulation_source_signature(scene, [piece])
    piece.SewingOutline = "[(0, 0), (120, 0), (100, 60), (0, 60)]"
    assert _simulation_source_signature(scene, [piece]) != moved


def test_signature_changes_when_seam_topology_or_sampling_changes():
    piece_a = _Piece("A", "piece-a")
    piece_b = _Piece("B", "piece-b")
    seam = _Seam()
    scene = _Scene([seam])
    baseline = _simulation_source_signature(scene, [piece_a, piece_b])

    seam.ReversedB = True
    assert _simulation_source_signature(scene, [piece_a, piece_b]) != baseline

    reversed_signature = _simulation_source_signature(scene, [piece_a, piece_b])
    scene.StitchSamples = 12
    assert _simulation_source_signature(scene, [piece_a, piece_b]) != reversed_signature


def test_unrelated_seams_do_not_invalidate_selected_pattern_scene():
    piece_a = _Piece("A", "piece-a")
    piece_b = _Piece("B", "piece-b")
    unrelated = _Seam()
    unrelated.SeamId = "unrelated"
    unrelated.PieceA = "other-a"
    unrelated.PieceB = "other-b"
    scene = _Scene([unrelated])
    baseline = _simulation_source_signature(scene, [piece_a, piece_b])

    unrelated.ReversedB = True
    assert _simulation_source_signature(scene, [piece_a, piece_b]) == baseline
