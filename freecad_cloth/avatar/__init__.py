"""Cloth Avatar package — human mannequin and avatar geometry providers."""

# Keep package import side-effect free. Individual avatar modules import each
# other and the simulation layer, so eagerly importing every submodule here
# can create circular imports during FreeCAD document restoration.
__all__ = [
    "AvatarArrangement",
    "AvatarCollision",
    "AvatarCommands",
    "AvatarFitting",
    "AvatarGui",
    "AvatarModel",
    "AvatarProvider",
    "AvatarService",
    "FittingCommands",
]
