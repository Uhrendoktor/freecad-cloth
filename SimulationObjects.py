"""FreeCAD-facing deterministic cloth simulation scene objects."""
import ast


def _mesh_object(doc, name, label):
    import Mesh
    obj = doc.addObject("Mesh::Feature", name)
    obj.Label = label
    obj.addProperty("App::PropertyString", "ClothMeshType", "Simulation").ClothMeshType = "DrapedCloth"
    return obj


def _write_mesh(obj, positions, triangles):
    import FreeCAD as App
    import Mesh
    native = Mesh.Mesh()
    for a, b, c in triangles:
        native.addFacet(App.Vector(*positions[a]), App.Vector(*positions[b]), App.Vector(*positions[c]))
    obj.Mesh = native

# ... existing simulation implementation unchanged ...


def create_humanoid_avatar(doc, scale=1.0):
    """Create a deterministic, editable mannequin collision proxy for draping tests."""
    import Part, FreeCAD
    s = float(scale)
    if s <= 0:
        raise ValueError("avatar scale must be positive")
    parts = [
        Part.makeCylinder(28 * s, 70 * s, FreeCAD.Vector(0, 0, -30 * s)),
        Part.makeSphere(22 * s, FreeCAD.Vector(0, 0, 62 * s)),
        Part.makeCylinder(12 * s, 60 * s, FreeCAD.Vector(-40 * s, 0, 20 * s)),
        Part.makeCylinder(12 * s, 60 * s, FreeCAD.Vector(28 * s, 0, 20 * s)),
        Part.makeCylinder(14 * s, 75 * s, FreeCAD.Vector(-15 * s, 0, -105 * s)),
        Part.makeCylinder(14 * s, 75 * s, FreeCAD.Vector(1 * s, 0, -105 * s)),
    ]
    avatar = doc.addObject("Part::Feature", "HumanoidAvatar")
    avatar.Label = "Humanoid Avatar"
    avatar.Shape = Part.makeCompound(parts)
    avatar.addProperty("App::PropertyString", "AvatarType", "Avatar").AvatarType = "ParametricHumanoid"
    avatar.addProperty("App::PropertyFloat", "Scale", "Avatar").Scale = s
    return avatar


def create_avatar_collision(doc, source_obj=None, thickness=2.0, deflection=1.0):
    """Create a compatibility collision proxy; DrapeTarget is authoritative."""
    avatar = doc.addObject("App::FeaturePython", "AvatarCollision")
    avatar.Label = "Avatar Collision Proxy (Compatibility)"
    avatar.addProperty("App::PropertyString", "CollisionType", "Simulation").CollisionType = "SphereProxy"
    avatar.addProperty("App::PropertyLink", "SourceObject", "Simulation")
    avatar.addProperty("App::PropertyFloat", "CollisionThickness", "Simulation").CollisionThickness = float(thickness)
    avatar.addProperty("App::PropertyFloat", "CollisionDeflection", "Simulation").CollisionDeflection = float(deflection)
    avatar.addProperty("App::PropertyInteger", "CollisionVertexCount", "Simulation").CollisionVertexCount = 0
    avatar.addProperty("App::PropertyInteger", "CollisionTriangleCount", "Simulation").CollisionTriangleCount = 0
    if source_obj is None:
        source_obj = create_humanoid_avatar(doc)
    from AvatarCollision import surface_from_freecad
    surface = surface_from_freecad(source_obj, deflection, thickness)
    avatar.SourceObject = source_obj
    avatar.CollisionType = "MeshSurface"
    avatar.CollisionVertexCount = len(surface.vertices)
    avatar.CollisionTriangleCount = len(surface.triangles)
    return avatar


def set_avatar_collision_source(scene, source_obj, thickness=2.0, deflection=1.0):
    """Update compatibility avatar state while keeping DrapeTarget authoritative.

    The return value is deliberately the AvatarProxy object because callers use
    this function to populate AvatarProxy/CollisionProxy links. The DrapeTarget
    is updated as a side effect and remains the solver authority.
    """
    from DrapeTarget import create_drape_target, assign_drape_target
    target = getattr(scene, "DrapeTarget", None)
    if target is None:
        target = create_drape_target(scene.Document, source_obj, "Mannequin", deflection, thickness)
        scene.DrapeTarget = target
    else:
        target.CollisionThickness = float(thickness)
        target.CollisionDeflection = float(deflection)
        assign_drape_target(target, source_obj, "Mannequin")
    avatar = getattr(scene, "AvatarProxy", None)
    if avatar is None or getattr(avatar, "Name", "") == getattr(target, "Name", ""):
        avatar = create_avatar_collision(scene.Document, source_obj, thickness, deflection)
    else:
        avatar.SourceObject = source_obj
        avatar.CollisionThickness = float(thickness)
        avatar.CollisionDeflection = float(deflection)
        from AvatarCollision import surface_from_freecad
        surface = surface_from_freecad(source_obj, deflection, thickness)
        avatar.CollisionType = "MeshSurface"
        avatar.CollisionVertexCount = len(surface.vertices)
        avatar.CollisionTriangleCount = len(surface.triangles)
    scene.AvatarProxy = avatar
    scene.Document.recompute()
    return avatar


# The remainder of SimulationObjects.py is unchanged.
