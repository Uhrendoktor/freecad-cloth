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


def test_quality_proxy_preserves_solver_stitch_provenance():
    from types import SimpleNamespace

    from freecad_cloth.simulation import SimulationQualityRuntimeV2 as runtime

    class Backend:
        name = "xpbd-cpu"
        time = 0.0

        def positions(self):
            return ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

        def finite(self):
            return True

    class Base:
        def __init__(self):
            self.backend = None
            self.source_signature = None
            self.last_steps = 0
            self.seam_stitch_pairs = {}

    base = Base()
    proxy = runtime.QualitySimulationProxy()
    proxy._base_or_restore = lambda: base
    proxy._signature = staticmethod(lambda obj, pattern_ir=None: ("signature",))
    proxy._build_pattern_scene = lambda obj, pieces, signature, pattern_ir=None: (
        setattr(base, "backend", Backend()),
        setattr(base, "seam_stitch_pairs", {"seam-1": ((0, 1),)}),
    )
    proxy._apply_material = lambda obj: None
    proxy._apply_collision = lambda obj: None

    scene = SimpleNamespace(
        ClothPieces=[SimpleNamespace(PatternType="PatternPiece")],
        QualityPreset="Balanced",
        ParticleDistance=4.0,
        SolverIterations=8,
        SolverSubsteps=1,
        FabricDensity=150.0,
        FabricThickness=0.5,
        FabricStretch=0.02,
        FabricShear=0.02,
        FabricBend=0.01,
        FabricFriction=0.5,
        AvatarSkinOffset=0.0,
        DrapeTarget=None,
        Steps=0,
        DrapePanels=[],
        SimulatedTime=0.0,
        ParticleCount=0,
        FiniteState=False,
        Document=SimpleNamespace(Objects=[]),
    )

    import freecad_cloth.common.PatternIRDocumentAdapter as adapter
    original_compile = adapter.compile_pattern_ir
    adapter.compile_pattern_ir = lambda doc, pieces: SimpleNamespace(validate=lambda: None)
    try:
        proxy.execute(scene)
    finally:
        adapter.compile_pattern_ir = original_compile

    assert proxy.seam_stitch_pairs == {"seam-1": ((0, 1),)}
    assert proxy.seam_stitch_pairs is not base.seam_stitch_pairs


def test_quality_proxy_keeps_provenance_explicit_after_backend_handoff():
    from freecad_cloth.simulation import SimulationQualityRuntimeV2 as runtime

    class Base:
        seam_stitch_pairs = {"seam-2": ((2, 3), (4, 5))}

    proxy = runtime.QualitySimulationProxy()
    proxy._sync_seam_stitch_provenance(Base())

    assert proxy.seam_stitch_pairs == {"seam-2": ((2, 3), (4, 5))}
    assert "seam_stitch_pairs" in proxy.__dict__

    replacement = Base()
    replacement.seam_stitch_pairs = {}
    proxy._base_or_restore = lambda: replacement
    assert proxy.seam_stitch_pairs == {"seam-2": ((2, 3), (4, 5))}
