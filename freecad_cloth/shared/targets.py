"""Target-neutral collision references shared by avatar and generic geometry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DrapeTargetRef:
    """Persistable target identity; geometry itself remains owned by FreeCAD."""

    provider: str
    object_name: str
    object_label: str | None = None
    revision: int = 0
    surface_ids: tuple[str, ...] = ()

    def is_human(self) -> bool:
        """Provide the public is human operation."""
        return self.provider == "human"

    def is_freecad_object(self) -> bool:
        """Provide the public is freecad object operation."""
        return self.provider == "freecad"
