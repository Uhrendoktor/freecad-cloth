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
