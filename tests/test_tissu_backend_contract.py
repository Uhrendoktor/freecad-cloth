import math
import sys
import types



class _Particle:
    def __init__(self, position):
        self._position = tuple(position)

    def position(self):
        return self._position


class _System:
    def __init__(self, positions):
        self.particles = tuple(_Particle(position) for position in positions)


class _FakeSolver:
    def __init__(self):
        self.bending_calls = []
        self.pin_calls = []
        self.stitch_calls = []

    def add_bending_constraint(self, *args):
        self.bending_calls.append(args)

    def add_pin(self, *args):
        self.pin_calls.append(args)

    def add_stitch(self, *args):
        self.stitch_calls.append(args)


class _FakeMaterial:
    def __init__(self):
        self.bending = None


class _FakeInstance:
    def __init__(self, count):
        self._ids = list(range(count))

    def get_particle_indices(self):
        return self._ids


class _FakeFabric:
    def __init__(self, count):
        self.instance = _FakeInstance(count)
        self.material = _FakeMaterial()


class _FakeSimulation:
    last = None

    def __init__(self, **_kwargs):
        self.solver = _FakeSolver()
        _FakeSimulation.last = self

    def create_from_arrays(self, _name, _vertices, _triangles, material):
        self.material_argument = material
        return _FakeFabric(len(_vertices))


def test_tissu_signed_dihedral_angle_matches_flat_solver_convention():
    from freecad_cloth.simulation.TissuBackend import _tissu_signed_dihedral_angle

    angle = _tissu_signed_dihedral_angle(
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    assert math.isclose(abs(angle), math.pi, rel_tol=0.0, abs_tol=1e-12)


def test_tissu_backend_registers_public_api_bending_constraints_with_matching_rest_angle(
    monkeypatch,
):
    monkeypatch.setitem(sys.modules, "tissu", types.SimpleNamespace(Simulation=_FakeSimulation))

    from freecad_cloth.simulation.TissuBackend import TissuBackend

    backend = TissuBackend(
        _System(
            (
                (0.0, 0.0, 0.0),
                (100.0, 0.0, 0.0),
                (100.0, 100.0, 0.0),
                (0.0, 100.0, 0.0),
            )
        ),
        ((0, 1, 2), (0, 2, 3)),
    )

    simulation = _FakeSimulation.last
    assert simulation.material_argument["bending_compliance"] == 1e6
    assert len(simulation.solver.bending_calls) == 1
    call = simulation.solver.bending_calls[0]
    assert call[:4] == (0, 2, 1, 3)
    assert math.isclose(abs(call[4]), math.pi, rel_tol=0.0, abs_tol=1e-12)
    assert call[5] == 0.01
    assert backend._fabric.material.bending == 0.01
