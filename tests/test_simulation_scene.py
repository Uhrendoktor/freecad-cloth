from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMesh import triangulate
from freecad_cloth.simulation.SimulationScene import SimulationScene


def test_scene_is_constructed_from_pattern_mesh():
    mesh = triangulate(rectangle(100.0, 60.0))
    scene = SimulationScene.from_mesh(mesh, gravity=(0.0, 0.0, 0.0), pinned=(0, 1), iterations=12)
    assert len(scene.state.positions) == len(mesh.vertices)
    assert scene.state.inverse_masses[0] == 0.0
    assert scene.state.inverse_masses[2] == 1.0
    assert len(scene.solver.constraints) == len(mesh.boundary_edges()) + 1


def test_pinned_vertices_remain_fixed_while_free_vertices_move():
    mesh = triangulate(rectangle(100.0, 60.0))
    scene = SimulationScene.from_mesh(mesh, gravity=(0.0, 0.0, -1000.0), pinned=(0,), iterations=16)
    initial = tuple(scene.state.positions)
    scene.step(0.01)
    assert scene.state.positions[0] == initial[0]
    assert any(scene.state.positions[i][2] != initial[i][2] for i in range(1, len(initial)))


def test_step_many_rejects_negative_steps():
    scene = SimulationScene.from_mesh(triangulate(rectangle(10.0, 10.0)))
    try:
        scene.step_many(-1, 0.01)
    except ValueError:
        return
    raise AssertionError("negative steps should fail")


def test_stale_drape_target_recompute_guard_is_safe():
    from types import SimpleNamespace
    from freecad_cloth.simulation import SimulationStaleGuard
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy

    source = SimpleNamespace(
        Name="Body", Label="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=10.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
        ),
    )
    target = SimpleNamespace(
        TargetType="FreeCAD Geometry", SourceObject=source,
        CollisionDeflection=1.0, CollisionThickness=0.0,
        Enabled=True, CollisionVertexCount=3, CollisionTriangleCount=1,
        SourceSignature=repr(("Body", "Body", ("Shape", 123), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0)),
    )

    class FakeScene:
        DrapeTarget = target
        SimulationState = "READY_FOR_SIMULATION"
        InvalidationReason = ""

    SimulationStaleGuard.install()
    scene = FakeScene()
    SimulationProxy().execute(scene)
    assert scene.SimulationState == "STALE"
    assert "source, placement" in scene.InvalidationReason


def test_pin_selection_is_part_of_rebuild_signature():
    from types import SimpleNamespace
    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

    source = SimpleNamespace(Name="Body", Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123), Placement=SimpleNamespace(Base=SimpleNamespace(x=0.0, y=0.0, z=0.0), Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0))))
    target = SimpleNamespace(SourceObject=source, CollisionDeflection=1.0, CollisionThickness=0.0)
    scene_a = SimpleNamespace(DrapeTarget=target, PinSelection=["1", "2"], StitchSamples=8, Document=SimpleNamespace(Objects=[]))
    scene_b = SimpleNamespace(DrapeTarget=target, PinSelection=["3", "4"], StitchSamples=8, Document=SimpleNamespace(Objects=[]))
    assert _simulation_source_signature(scene_a, []) != _simulation_source_signature(scene_b, [])



def test_seam_pair_records_preserve_exact_solver_stitch_provenance():
    from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR, PieceIR, SeamIR
    from freecad_cloth.simulation.SimulationObjects import _seam_pair_records

    pattern = PatternIR(
        (
            PieceIR(
                "piece-a",
                "PieceA",
                (BoundaryIR("piece-a:edge:0", "line", ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0))),),
            ),
            PieceIR(
                "piece-b",
                "PieceB",
                (BoundaryIR("piece-b:edge:0", "line", ((0.0, 100.0, 0.0), (20.0, 100.0, 0.0))),),
            ),
        ),
        (
            SeamIR(
                id="seam-1",
                piece_a="piece-a",
                edge_a="piece-a:edge:0",
                piece_b="piece-b",
                edge_b="piece-b:edge:0",
                reversed_b=True,
            ),
        ),
    )
    panel_data = {
        "piece-a": {
            "boundary_edges": ((0, 1, 2),),
            "positions": (
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
            ),
        },
        "piece-b": {
            "boundary_edges": ((3, 4, 5),),
            "positions": (
                (0.0, 100.0, 0.0),
                (10.0, 100.0, 0.0),
                (20.0, 100.0, 0.0),
            ),
        },
    }
    pairs, records = _seam_pair_records(pattern, panel_data, seam_samples=3)
    assert pairs == ((0, 5), (1, 4), (2, 3))
    assert records == (
        ("seam-1", "PieceA", "PieceB", ((0, 5), (1, 4), (2, 3))),
    )


def test_simulation_proxy_does_not_mix_surface_and_legacy_sphere_collision():
    from types import SimpleNamespace
    from freecad_cloth.simulation.SimulationObjects import SimulationProxy, _simulation_source_signature

    class FakeBackend:
        def __init__(self):
            self.calls = []

        def step(self, dt, iterations, gravity, sphere, surface):
            self.calls.append((dt, iterations, gravity, sphere, surface))

        def positions(self):
            return ()

        @property
        def time(self):
            return 0.0

        def finite(self):
            return True

    scene = SimpleNamespace(
        ClothPieces=[],
        Document=SimpleNamespace(Objects=[]),
        DrapeTarget=None,
        PinSelection=[],
        StitchSamples=8,
        Steps=1,
        TimeStep=1.0 / 60.0,
        Iterations=8,
        GravityX=0.0,
        GravityY=0.0,
        GravityZ=-9810.0,
        CollisionX=0.0,
        CollisionY=0.0,
        CollisionZ=0.0,
        CollisionRadius=38.0,
        DrapePanels=[],
    )
    proxy = SimulationProxy()
    proxy.backend = FakeBackend()
    proxy.collision_surface = object()
    proxy.source_signature = _simulation_source_signature(scene, [])
    proxy.execute(scene)

    assert proxy.backend.calls == [
        (
            scene.TimeStep,
            scene.Iterations,
            (scene.GravityX, scene.GravityY, scene.GravityZ),
            None,
            proxy.collision_surface,
        )
    ]
