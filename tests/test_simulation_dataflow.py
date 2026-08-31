"""Regression tests for Pattern/Sewing -> Simulation source invalidation."""

from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature


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
