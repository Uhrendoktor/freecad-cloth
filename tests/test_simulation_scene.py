from PatternGeometry import rectangle
from PatternMesh import triangulate
from SimulationScene import SimulationScene


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
    import SimulationStaleGuard
    from SimulationObjects import SimulationProxy

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


if __name__ == "__main__":
    test_scene_is_constructed_from_pattern_mesh()
    test_pinned_vertices_remain_fixed_while_free_vertices_move()
    test_step_many_rejects_negative_steps()
    test_stale_drape_target_recompute_guard_is_safe()
    print("simulation scene tests passed")
