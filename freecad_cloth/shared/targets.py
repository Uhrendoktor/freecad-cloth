# Copyright (C) 2026 FreeCAD Cloth contributors
"""Target-neutral collision references shared by avatar and generic geometry."""

from pydantic.dataclasses import dataclass as pydantic_dataclass


@pydantic_dataclass(frozen=True)
class DrapeTargetRef:
    """Persistable target identity; geometry itself remains owned by FreeCAD."""

    provider: str
    object_name: str
    object_label: str | None = None
    revision: int = 0
    surface_ids: tuple[str, ...] = ()

    def is_human(self) -> bool:
        """Determine whether this reference identifies the human mannequin.

        Returns:
            True when the target provider is the human mannequin, otherwise False.
        """
        return self.provider == "human"

    def is_freecad_object(self) -> bool:
        """Determine whether this reference identifies a native FreeCAD object.

        Returns:
            True when the target provider is a FreeCAD object, otherwise False.
        """
        return self.provider == "freecad"
