"""Small adapter contract for the production Tissu cloth solver.

FreeCAD document code depends on this boundary instead of importing Tissu APIs.
Tissu is the only runtime solver; the headless ClothSystem is only input data.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from freecad_cloth.avatar.AvatarCollision import CollisionSurface

PINNED_STITCH_EPSILON_MM = 1.0e-9


def _position_tuple(value):
    position = value.position() if callable(getattr(value, "position", None)) else value
    values = tuple(float(component) for component in position)
    if len(values) != 3:
        raise ValueError("simulation stitch positions must be three-dimensional")
    return values


def validate_pinned_stitch_pairs(
    positions,
    pinned_indices,
    seam_pair_records=(),
    *,
    epsilon=PINNED_STITCH_EPSILON_MM,
):
    """Reject impossible non-zero stitches between already pinned particles."""
    positions = tuple(_position_tuple(value) for value in positions)
    pinned = frozenset(int(index) for index in pinned_indices)
    if epsilon < 0.0:
        raise ValueError("stitch validation epsilon must be non-negative")

    candidates = (
        (str(record[0]), pair) for record in tuple(seam_pair_records) for pair in record[3]
    )
    seen = set()
    for seam_id, pair in candidates:
        a, b = (int(pair[0]), int(pair[1]))
        if a < 0 or b < 0 or a >= len(positions) or b >= len(positions):
            raise ValueError(
                "stitch pair is outside the simulation particle set: "
                f"seam={seam_id} particle_a={a} particle_b={b}"
            )
        pair_key = (a, b)
        if pair_key in seen:
            continue
        seen.add(pair_key)
        if a not in pinned or b not in pinned:
            continue
        pa, pb = positions[a], positions[b]
        separation = sum((pa[index] - pb[index]) ** 2 for index in range(3)) ** 0.5
        if separation > epsilon:
            raise ValueError(
                "impossible pinned-pinned sewing constraint: "
                f"seam={seam_id} particle_a={a} particle_b={b} "
                f"initial_separation={separation:.9f} mm"
            )


class ClothSimulationBackend(ABC):
    """Runtime contract implemented by the production solver backend."""

    name = "abstract"

    @property
    def solver_collision_surface(self) -> CollisionSurface | None:
        """Return the collision surface registered with the backend."""
        return None

    @abstractmethod
    def step(
        self,
        dt=1.0 / 60.0,
        iterations=8,
        gravity=(0.0, 0.0, -9810.0),
        surface=None,
    ):
        """Advance the simulation by one time step."""
        raise NotImplementedError

    @abstractmethod
    def reset(self):
        """Reset solver state to its last constructed input."""
        raise NotImplementedError

    @abstractmethod
    def pin(self, indices: Iterable[int]):
        """Replace the set of pinned particle indices."""
        raise NotImplementedError

    @abstractmethod
    def set_stitches(self, pairs: Iterable[tuple[int, int]], compliance=0.0):
        """Replace the sewing constraints."""
        raise NotImplementedError

    @abstractmethod
    def positions(self):
        """Return current particle positions in FreeCAD millimetres."""
        raise NotImplementedError

    @abstractmethod
    def finite(self):
        """Report whether all solver positions are within the accepted finite bound."""
        raise NotImplementedError

    @property
    @abstractmethod
    def time(self):
        """Return elapsed simulation time in seconds."""
        raise NotImplementedError
