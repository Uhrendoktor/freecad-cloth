"""Stable solver-neutral interface for the parametric Cloth avatar.

The service deliberately exposes derived geometry through the existing
FreeCAD-independent AvatarModel. FreeCAD document objects can adapt to this
interface without coupling the solver to Part/OpenCascade construction details.
"""
from AvatarModel import AvatarParameters, Landmark, generate_mesh


class AvatarService:
    """Read-only fitting/simulation view of an :class:`AvatarParameters` state."""

    def __init__(self, parameters=None):
        self._parameters = parameters if parameters is not None else AvatarParameters()
        if not isinstance(self._parameters, AvatarParameters):
            raise TypeError("AvatarService requires AvatarParameters")

    def parameters(self):
        """Return the authoritative immutable parameter state."""
        return self._parameters

    def surface(self):
        """Return the deterministic visual surface as ``(vertices, triangles)``."""
        vertices, triangles, _landmarks = generate_mesh(self._parameters)
        return vertices, triangles

    def collision_mesh(self):
        """Return the collision representation derived from the same state.

        The reference mannequin currently uses the same deterministic mesh for
        both views; its configurable skin offset is already incorporated by
        ``AvatarModel.generate_mesh``. A coarser collision adapter can replace
        this method later without changing downstream callers.
        """
        return self.surface()

    def landmarks(self):
        """Return all stable named landmarks as ``Landmark`` instances."""
        return generate_mesh(self._parameters)[2]

    def landmark(self, name):
        """Return one stable landmark or raise ``KeyError``."""
        key = str(name)
        for landmark in self.landmarks():
            if landmark.name == key:
                return landmark
        raise KeyError(key)

    def measurement(self, name):
        return self._parameters.measurement(str(name))

    def measurements(self):
        """Return a sorted immutable-ish snapshot of anthropometric values."""
        return tuple(sorted((name, float(value)) for name, value in self._parameters.measurements.items()))

    def pose(self):
        return self._parameters.pose

    def skin_offset(self):
        return float(self._parameters.skin_offset)
