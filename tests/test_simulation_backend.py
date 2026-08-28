from PatternModel import AssemblyTransform, Seam, SeamGraph
from SimulationBackend import BackendRegistry, ClothState, NullSolver, default_backend_registry


def test_seam_graph_preserves_stable_ids_and_transform():
    seam = Seam("front", 1, "back", 2, id="shoulder", reversed_b=True)
    transform = AssemblyTransform((10.0, 0.0, 2.0), 15.0)
    graph = SeamGraph([seam], {"shoulder": transform})
    assert graph.by_id()["shoulder"] is seam
    assert graph.transform_for("shoulder") == transform


def test_seam_graph_rejects_unknown_transform():
    try:
        SeamGraph([], {"missing": AssemblyTransform()})
    except ValueError:
        return
    raise AssertionError("unknown seam transform must be rejected")


def test_backend_registry_is_dependency_free_and_extensible():
    registry = default_backend_registry()
    assert registry.names() == ("null",)
    state = ClothState([(0.0, 0.0, 0.0)])
    assert isinstance(registry.create("null"), NullSolver)
    registry.register("test", NullSolver)
    assert registry.create("TEST").step(state, 0.01) is state


def test_backend_registry_rejects_duplicate_and_unknown_names():
    registry = BackendRegistry()
    registry.register("null", NullSolver)
    try:
        registry.register("NULL", NullSolver)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate backend names must be rejected")
    try:
        registry.create("missing")
    except KeyError:
        return
    raise AssertionError("unknown backend must be rejected")


if __name__ == "__main__":
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("simulation backend tests passed")
