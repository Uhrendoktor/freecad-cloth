"""Target-neutral collision references shared by avatar and generic geometry."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CollisionSurface:
    """Immutable description of a collision surface used by simulation adapters."""

    provider_id: str
    object_name: str
    revision: int = 0
    offset_mm: float = 3.0


@dataclass(frozen=True)
class DrapeTargetRef:
    """Persistable target identity; geometry itself remains owned by FreeCAD."""

    provider: str
    object_name: str
    object_label: Optional[str] = None
    revision: int = 0
    surface_ids: Tuple[str, ...] = ()

    def is_human(self) -> bool:
        return self.provider == "human"

    def is_freecad_object(self) -> bool:
        return self.provider == "freecad"
