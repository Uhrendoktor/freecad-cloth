# Copyright (C) 2026 FreeCAD Cloth contributors
"""Stable solver-neutral interface for the parametric Cloth avatar.

The service exposes geometry from the FreeCAD-independent AvatarModel.
Document adapters and simulation providers share one typed mesh and landmark
contract without depending on Part or OpenCascade.
"""

from freecad_cloth.avatar.AvatarModel import AvatarParameters, Landmark, Pose, generate_mesh

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
AvatarSurface = tuple[tuple[Point3, ...], tuple[Triangle, ...]]


class AvatarService:
    """Read-only fitting and simulation view of an AvatarParameters state."""

    def __init__(self, parameters: AvatarParameters | None = None) -> None:
        """Create a service for one canonical avatar parameter state.

        Args:
            parameters: Optional immutable state; omitted values use standard defaults.

        Raises:
            TypeError: If parameters is not an AvatarParameters instance.
        """
        self._parameters = parameters if parameters is not None else AvatarParameters()
        if not isinstance(self._parameters, AvatarParameters):
            msg = "AvatarService requires AvatarParameters"
            raise TypeError(msg)

    def parameters(self) -> AvatarParameters:
        """Return the authoritative parameter state.

        Returns:
            The parameter object used by every derived service result.
        """
        return self._parameters

    def surface(self) -> AvatarSurface:
        """Return the deterministic visual mesh.

        Returns:
            Immutable vertex coordinates and triangle indices.
        """
        vertices, triangles, _landmarks = generate_mesh(self._parameters)
        return vertices, triangles

    def collision_mesh(self) -> AvatarSurface:
        """Return collision geometry derived from the same parameter state.

        The reference mannequin currently uses its visual mesh for collision;
        its configured skin offset is already included by generate_mesh.
        A coarser collision mesh can replace this method without changing callers.

        Returns:
            Immutable collision vertices and triangle indices.
        """
        return self.surface()

    def landmarks(self) -> tuple[Landmark, ...]:
        """Return all stable named landmarks.

        Returns:
            Semantic landmark coordinates generated from the same avatar state.
        """
        return generate_mesh(self._parameters)[2]

    def landmark(self, name: str) -> Landmark:
        """Return one stable landmark by name.

        Args:
            name: Exact canonical landmark name.

        Returns:
            The landmark associated with name.

        Raises:
            KeyError: If the avatar defines no landmark with that name.
        """
        key = str(name)
        for landmark in self.landmarks():
            if landmark.name == key:
                return landmark
        raise KeyError(key)

    def measurement(self, name: str) -> float:
        """Return one requested body measurement.

        Args:
            name: Canonical measurement field.

        Returns:
            The measurement in millimetres.

        Raises:
            KeyError: If name is not a supported measurement.
        """
        return self._parameters.measurement(str(name))

    def measurements(self) -> tuple[tuple[str, float], ...]:
        """Return a deterministic snapshot of anthropometric measurements.

        Returns:
            Sorted name/value pairs in millimetres.
        """
        return tuple(
            sorted((name, float(value)) for name, value in self._parameters.measurements.items())
        )

    def pose(self) -> Pose:
        """Return the canonical pose settings.

        Returns:
            The immutable preset and joint-rotation state.
        """
        return self._parameters.pose

    def skin_offset(self) -> float:
        """Return the visible avatar skin offset.

        Returns:
            Skin offset in millimetres.
        """
        return float(self._parameters.skin_offset)
