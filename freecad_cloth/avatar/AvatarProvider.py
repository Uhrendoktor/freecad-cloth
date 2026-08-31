"""Replaceable avatar-provider contract for the Cloth fitting/simulation stack.

The provider boundary deliberately knows nothing about FreeCAD document objects
or solver implementation details.  A provider supplies an authoritative
parameter/identity snapshot, a visual surface, a collision surface, and stable
landmarks.  The parametric mannequin is the built-in provider; a CAD provider
adapts an existing FreeCAD object through the target-neutral DrapeTarget API.
"""
from dataclasses import dataclass

from freecad_cloth.avatar.AvatarService import AvatarService
from freecad_cloth.simulation.DrapeTarget import collision_surface


@dataclass(frozen=True)
class AvatarProviderInfo:
    """Persistent identity presented by the avatar UI/document layer."""

    provider_id: str
    display_name: str
    fidelity: str


class AvatarProvider:
    """Minimal provider protocol consumed by fitting and target adapters."""

    info = AvatarProviderInfo("unknown", "Unknown", "unknown")

    def parameters(self):
        raise NotImplementedError

    def surface(self):
        raise NotImplementedError

    def collision_surface(self):
        raise NotImplementedError

    def landmarks(self):
        raise NotImplementedError


class ParametricAvatarProvider(AvatarProvider):
    """Built-in deterministic human mannequin provider."""

    info = AvatarProviderInfo("parametric-mannequin", "Parametric human mannequin", "baseline")

    def __init__(self, parameters=None):
        self._service = AvatarService(parameters)

    def parameters(self):
        return self._service.parameters()

    def surface(self):
        return self._service.surface()

    def collision_surface(self):
        return self._service.collision_mesh()

    def landmarks(self):
        return self._service.landmarks()


class FreeCADGeometryAvatarProvider(AvatarProvider):
    """Adapter for an imported/native FreeCAD body without a hard dependency.

    The object is intentionally opaque to the provider contract.  Collision
    tessellation is delegated to the existing DrapeTarget surface adapter, so
    Sewing and Simulation do not need to know whether the body came from the
    native mannequin, Part, PartDesign, or Mesh workbench.
    """

    info = AvatarProviderInfo("freecad-geometry", "FreeCAD body", "external")

    def __init__(self, source, deflection=1.0, thickness=0.0):
        if source is None:
            raise ValueError("a FreeCAD geometry avatar provider requires a source")
        self.source = source
        self.deflection = float(deflection)
        self.thickness = float(thickness)
        if self.deflection <= 0:
            raise ValueError("deflection must be positive")
        if self.thickness < 0:
            raise ValueError("thickness must not be negative")

    def parameters(self):
        """CAD providers have no anthropometric authority."""
        return None

    def surface(self):
        """Return the target-neutral collision surface as the visual fallback."""
        surface = collision_surface(self.source, self.deflection, self.thickness)
        return surface.vertices, surface.triangles

    def collision_surface(self):
        return self.surface()

    def landmarks(self):
        return ()


def provider_from_target(source, target_type="FreeCAD Geometry", parameters=None,
                         deflection=1.0, thickness=0.0):
    """Build the appropriate provider without coupling callers to a class.

    ``Mannequin`` remains the deterministic built-in provider.  Any other
    accepted target type currently resolves to the generic FreeCAD adapter.
    This keeps provider selection replaceable while preserving the public
    DrapeTarget/Sewing APIs.
    """
    kind = str(target_type)
    if kind == "Mannequin":
        return ParametricAvatarProvider(parameters)
    if kind == "FreeCAD Geometry":
        return FreeCADGeometryAvatarProvider(source, deflection, thickness)
    raise ValueError("unsupported avatar provider target type: %s" % kind)
