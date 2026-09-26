"""FreeCAD-facing body measurement, avatar fitting, and arrangement commands."""
import hashlib
import json


def _scene(doc):
    return next((o for o in doc.Objects if getattr(o, "FittingType", "") == "FittingScene"), None)


def _safe_name(value):
    return "".join(ch if ch.isalnum() else "_" for ch in str(value)) or "Item"


def _sync_visuals(scene):
    """Synchronize visible FreeCAD point/volume adapters from canonical strings."""
    import FreeCAD as App
    import Part
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint, BoundingVolume

    points = tuple(ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)
    volumes = tuple(BoundingVolume.from_string(v) for v in scene.BoundingVolumes)
    point_objects = []
    volume_objects = []
    existing = {o.Name: o for o in scene.Document.Objects}
    for point in points:
        name = "ArrangementPoint_" + _safe_name(point.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Arrangement: " + point.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "ArrangementPoint"
        for prop, value in (("PointName", point.name), ("WrapDirection", point.wrap_direction), ("SymmetryGroup", point.symmetry_group)):
            if not hasattr(obj, prop):
                obj.addProperty("App::PropertyString", prop, "Fitting")
            setattr(obj, prop, value)
        if not hasattr(obj, "X"):
            obj.addProperty("App::PropertyDistance", "X", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Y", "Arrangement")
            obj.addProperty("App::PropertyDistance", "Offset", "Arrangement")
            obj.addProperty("App::PropertyAngle", "RotationZ", "Arrangement")
        obj.X, obj.Y, obj.Offset, obj.RotationZ = point.x, point.y, point.offset, point.rotation_z
        obj.Shape = Part.makeSphere(4.0, App.Vector(point.x, point.y, point.offset))
        point_objects.append(obj)
    for volume in volumes:
        name = "BoundingVolume_" + _safe_name(volume.name)
        obj = existing.get(name) or scene.Document.addObject("Part::Feature", name)
        obj.Label = "Bounding Volume: " + volume.name
        if not hasattr(obj, "FittingType"):
            obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "BoundingVolume"
        if not hasattr(obj, "VolumeName"):
            obj.addProperty("App::PropertyString", "VolumeName", "Fitting")
            obj.addProperty("App::PropertyVector", "Center", "Volume")
            obj.addProperty("App::PropertyVector", "Size", "Volume")
        obj.VolumeName = volume.name
        obj.Center = App.Vector(*volume.center)
        obj.Size = App.Vector(*volume.size)
        corner = App.Vector(
            volume.center[0] - volume.size[0] / 2.0,
            volume.center[1] - volume.size[1] / 2.0,
            volume.center[2] - volume.size[2] / 2.0,
        )
        obj.Shape = Part.makeBox(volume.size[0], volume.size[1], volume.size[2], corner)
        volume_objects.append(obj)
    scene.ArrangementPointObjects = [obj.Name for obj in point_objects]
    scene.BoundingVolumeObjects = [obj.Name for obj in volume_objects]
    for obj in point_objects + volume_objects:
        obj.ViewObject.Visibility = True



def _migrate_visual_output_references(scene):
    """Convert legacy visual-object links to persisted object-name outputs.

    ArrangementPointObjects and BoundingVolumeObjects are derived visual outputs,
    not dependency inputs. Persisting them as links makes the FittingScene proxy
    depend on objects that the proxy itself mutates during execution, which is a
    reverse dependency that FreeCAD reports as an object still touched after
    recompute. Existing documents keep the property names but migrate their
    values to non-dependency string outputs before proxy execution.
    """
    for name in ("ArrangementPointObjects", "BoundingVolumeObjects"):
        if name not in getattr(scene, "PropertiesList", ()):
            scene.addProperty("App::PropertyStringList", name, "Arrangement")
            setattr(scene, name, [])
            continue
        try:
            type_id = scene.getTypeIdOfProperty(name)
        except (AttributeError, RuntimeError):
            type_id = ""
        if str(type_id) == "App::PropertyStringList":
            continue
        legacy = tuple(getattr(scene, name, ()) or ())
        names = [getattr(item, "Name", "") for item in legacy if getattr(item, "Name", "")]
        scene.removeProperty(name)
        scene.addProperty("App::PropertyStringList", name, "Arrangement")
        setattr(scene, name, names)

def create_fitting_scene():
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    if _scene(doc) is not None:
        return _scene(doc)
    obj = doc.addObject("App::FeaturePython", "FittingScene")
    obj.Label = "Avatar Fitting Scene"
    obj.addProperty("App::PropertyString", "FittingType", "Fitting").FittingType = "FittingScene"
    obj.addProperty("App::PropertyString", "MeasurementData", "Measurements").MeasurementData = BodyMeasurements().to_json()
    obj.addProperty("App::PropertyString", "MeasurementUnit", "Measurements").MeasurementUnit = "mm"
    obj.addProperty("App::PropertyLink", "AvatarProxy", "Fitting")
    obj.addProperty("App::PropertyLinkListGlobal", "PatternPieces", "Fitting")
    obj.addProperty("App::PropertyLinkGlobal", "DrapeTarget", "Fitting")
    obj.addProperty("App::PropertyStringList", "PiecePlacements", "Fitting").PiecePlacements = []
    obj.addProperty("App::PropertyStringList", "HomePlacements", "Fitting").HomePlacements = []
    obj.addProperty("App::PropertyStringList", "ArrangementPoints", "Arrangement").ArrangementPoints = []
    obj.addProperty("App::PropertyStringList", "BoundingVolumes", "Arrangement").BoundingVolumes = []
    obj.addProperty("App::PropertyStringList", "ArrangementPointObjects", "Arrangement").ArrangementPointObjects = []
    obj.addProperty("App::PropertyStringList", "BoundingVolumeObjects", "Arrangement").BoundingVolumeObjects = []
    obj.addProperty("App::PropertyBool", "SymmetryEnabled", "Arrangement").SymmetryEnabled = True
    obj.addProperty("App::PropertyString", "TargetPlacementSignature", "Arrangement").TargetPlacementSignature = ""
    obj.addProperty("App::PropertyFloat", "TargetPlacementClearance", "Arrangement").TargetPlacementClearance = 0.0
    obj.addProperty("App::PropertyString", "FitStatus", "Fitting").FitStatus = "Unassigned"
    obj.Proxy = _FittingProxy()
    FittingScene().validate()
    doc.recompute()
    return obj


def set_body_measurements(measurements, unit="mm"):
    from freecad_cloth.avatar.AvatarFitting import BodyMeasurements
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    data = BodyMeasurements(dict(measurements), unit)
    data.validate()
    scene.MeasurementData = data.to_json()
    scene.MeasurementUnit = data.unit
    scene.FitStatus = "Measurements set"
    doc.recompute()
    return scene


def assign_avatar_source(source=None):
    import FreeCAD as App
    import FreeCADGui as Gui
    from freecad_cloth.simulation.SimulationObjects import create_avatar_collision, set_avatar_collision_source

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if source is None:
        source = next((o for o in Gui.Selection.getSelection() if hasattr(o, "Shape") or hasattr(o, "Mesh")), None)
    if source is None:
        raise ValueError("select a FreeCAD body or mesh to use as the avatar source")
    avatar = create_avatar_collision(doc) if doc.getObject("AvatarCollision") is None else doc.getObject("AvatarCollision")
    avatar = set_avatar_collision_source(scene, source)
    scene.AvatarProxy = avatar
    scene.FitStatus = "Avatar assigned"
    doc.recompute()
    return scene


def add_selected_pattern_pieces():
    import FreeCAD as App
    import FreeCADGui as Gui
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement, FittingScene, BodyMeasurements

    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    pieces = [o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"]
    if not pieces:
        raise ValueError("select one or more pattern pieces before adding them to the fitting scene")
    existing = [PiecePlacement.from_string(v) for v in scene.PiecePlacements]
    homes = [PiecePlacement.from_string(v) for v in scene.HomePlacements]
    by_id = {p.piece_id: p for p in existing}
    home_by_id = {p.piece_id: p for p in homes}
    for piece in pieces:
        placement = piece.Placement
        base = placement.Base
        rotation = placement.Rotation
        axis = rotation.Axis
        value = PiecePlacement(
            str(piece.PieceId),
            (float(base.x), float(base.y), float(base.z)),
            float(rotation.Angle),
            (float(axis.x), float(axis.y), float(axis.z)),
        )
        by_id[value.piece_id] = value
        home_by_id.setdefault(value.piece_id, value)
    scene.PatternPieces = sorted(set(list(scene.PatternPieces) + pieces), key=lambda o: str(o.PieceId))
    scene.PiecePlacements = [by_id[k].to_string() for k in sorted(by_id)]
    scene.HomePlacements = [home_by_id[k].to_string() for k in sorted(home_by_id)]
    FittingScene(BodyMeasurements.from_json(scene.MeasurementData), getattr(scene.AvatarProxy, "Label", "") if scene.AvatarProxy else "", tuple(by_id.values())).validate()
    scene.FitStatus = "Ready" if scene.AvatarProxy else "Pieces assigned"
    doc.recompute()
    return scene


def position_piece(piece, x, y, z=0.0, rotation_z=0.0):
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    placement = App.Placement(App.Vector(float(x), float(y), float(z)), App.Rotation(App.Vector(0, 0, 1), float(rotation_z)))
    piece.Placement = placement
    entries = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)}
    entries[str(piece.PieceId)] = PiecePlacement(str(piece.PieceId), (float(x), float(y), float(z)), float(rotation_z))
    scene.PiecePlacements = [entries[k].to_string() for k in sorted(entries)]
    doc.recompute()
    return piece


def _pattern_points(piece):
    from freecad_cloth.common.PatternSimulationAdapter import geometry_from_piece_ir, resolve_piece_ir
    from freecad_cloth.pattern.PatternMesh import triangulate

    mesh = triangulate(geometry_from_piece_ir(resolve_piece_ir(piece)))
    return tuple((float(x), float(y), 0.0) for x, y in mesh.vertices)


def _pattern_bounds(piece):
    points = _pattern_points(piece)
    if not points:
        raise ValueError("pattern piece has no triangulated vertices")
    return (
        min(p[0] for p in points), max(p[0] for p in points),
        min(p[1] for p in points), max(p[1] for p in points),
    )


def _placement_record(piece):
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement

    placement = piece.Placement
    base = placement.Base
    axis = placement.Rotation.Axis
    return PiecePlacement(
        str(piece.PieceId),
        (float(base.x), float(base.y), float(base.z)),
        float(placement.Rotation.Angle),
        (float(axis.x), float(axis.y), float(axis.z)),
    )


def _world_points(piece, local_points, translation=(0.0, 0.0, 0.0)):
    import FreeCAD as App

    placement = piece.Placement
    return tuple(
        (
            float(world.x) + float(translation[0]),
            float(world.y) + float(translation[1]),
            float(world.z) + float(translation[2]),
        )
        for world in (
            placement.multVec(App.Vector(*point))
            for point in local_points
        )
    )


def _resolve_single_target(doc, target=None):
    from freecad_cloth.simulation.DrapeTarget import target_status

    candidates = [
        obj for obj in doc.Objects
        if getattr(obj, "TargetType", "") in ("Mannequin", "FreeCAD Geometry")
        and hasattr(obj, "SourceObject")
    ]
    if target is None:
        if len(candidates) != 1:
            raise ValueError(
                "target-aware placement requires exactly one explicit DrapeTarget; "
                "found %d candidate targets" % len(candidates)
            )
        target = candidates[0]
    if target not in candidates:
        raise ValueError("selected placement target is not a persistent DrapeTarget")
    status = target_status(target)
    if status["state"] != "ready":
        raise ValueError("cannot arrange against DrapeTarget: %s" % status["message"])
    return target


def snap_pattern_pieces_to_target(
    pieces=None,
    target=None,
    *,
    clearance=8.0,
    max_translation=350.0,
    max_rotation_degrees=15.0,
    anchor_profiles=None,
):
    """Place pattern pieces rigidly around one current DrapeTarget.

    The operation only changes persistent PatternPiece placements. It refuses
    missing, stale, disabled or ambiguous targets, preserves each piece's exact
    home transform, and creates no solver pins.
    """
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    from freecad_cloth.avatar.TargetAwarePlacement import (
        TargetPlacementError,
        minimum_signed_clearance,
        signature_payload,
        solve_rigid_translation,
        tunic_anchor_profile,
    )
    from freecad_cloth.simulation.DrapeTarget import collision_surface, source_signature

    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before arranging garment pieces")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene before arranging garment pieces")
    target = _resolve_single_target(doc, target)
    surface = collision_surface(
        target.SourceObject,
        float(target.CollisionDeflection),
        float(target.CollisionThickness),
    )
    if float(clearance) < 0.0:
        raise ValueError("placement clearance must not be negative")
    selected = tuple(
        sorted(
            (
                piece for piece in (pieces or scene.PatternPieces)
                if getattr(piece, "PatternType", "") == "PatternPiece"
            ),
            key=lambda item: str(getattr(item, "PieceId", item.Name)),
        )
    )
    if not selected:
        raise ValueError("no PatternPiece objects were supplied")
    if len({str(piece.PieceId) for piece in selected}) != len(selected):
        raise ValueError("target-aware placement requires unique PatternPiece IDs")

    existing = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.PiecePlacements)}
    homes = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.HomePlacements)}
    for piece in selected:
        pid = str(piece.PieceId)
        current = _placement_record(piece)
        existing[pid] = current
        homes.setdefault(pid, current)

    target_center = surface.center
    profiles = {}
    if anchor_profiles is not None:
        profiles.update({str(key): value for key, value in anchor_profiles.items()})

    plans = []
    for piece in selected:
        pid = str(piece.PieceId)
        bounds = _pattern_bounds(piece)
        width = bounds[1] - bounds[0]
        height = bounds[3] - bounds[2]
        profile = profiles.get(pid)
        if profile is None:
            current_points = _world_points(piece, ((0.5 * (bounds[0] + bounds[1]), 0.5 * (bounds[2] + bounds[3]), 0.0),))
            primary = "front" if current_points[0][1] <= target_center[1] else "back"
            profile = tunic_anchor_profile(width, height, primary)
        profile.validate()
        world_anchors = {
            anchor.name: _world_points(piece, (anchor.local_position,))[0]
            for anchor in profile.anchors
        }
        try:
            solution = solve_rigid_translation(
                world_anchors,
                profile,
                surface,
                clearance=float(clearance),
                max_translation=float(max_translation),
                max_rotation_degrees=float(max_rotation_degrees),
            )
        except TargetPlacementError as exc:
            raise ValueError("target-aware placement for %s rejected: %s" % (pid, exc)) from exc

        local_points = _pattern_points(piece)
        moved_points = _world_points(piece, local_points, solution.translation)
        measured = minimum_signed_clearance(moved_points, surface, sample_limit=128)
        if measured is None or measured < float(clearance) - 1e-6:
            from freecad_cloth.avatar.TargetAwarePlacement import wrap_vector

            correction = float(clearance) - float(measured if measured is not None else 0.0)
            direction = wrap_vector(profile.primary_wrap_direction)
            corrected = tuple(
                float(solution.translation[index]) + float(direction[index]) * correction
                for index in range(3)
            )
            corrected_length = sum(value * value for value in corrected) ** 0.5
            if corrected_length > float(max_translation) + 1e-9:
                raise ValueError("target-aware placement for %s exceeds translation bound while enforcing clearance" % pid)
            moved_points = _world_points(piece, local_points, corrected)
            measured = minimum_signed_clearance(moved_points, surface, sample_limit=128)
            if measured is None or measured < float(clearance) - 1e-6:
                raise ValueError("target-aware placement for %s cannot prove step-0 target clearance" % pid)
            solution = type(solution)(
                corrected,
                solution.rotation_degrees,
                solution.minimum_anchor_clearance,
                solution.maximum_anchor_residual,
                solution.probes,
            )

        base = piece.Placement.Base
        new_position = tuple(
            float(base[index]) + float(solution.translation[index])
            for index in range(3)
        )
        plans.append((piece, pid, profile, solution, new_position, float(measured)))

    # Commit atomically after every target/profile/guard/clearance check succeeds.
    old_placements = {str(piece.PieceId): piece.Placement for piece in selected}
    old_piece_values = dict(existing)
    old_home_values = dict(homes)
    old_signature = getattr(scene, "TargetPlacementSignature", "") if hasattr(scene, "TargetPlacementSignature") else ""
    old_clearance = getattr(scene, "TargetPlacementClearance", 0.0) if hasattr(scene, "TargetPlacementClearance") else 0.0
    try:
        for piece, pid, _profile, solution, new_position, _measured in plans:
            piece.Placement = App.Placement(
                App.Vector(*new_position),
                piece.Placement.Rotation,
            )
            existing[pid] = _placement_record(piece)

        scene.PatternPieces = sorted(
            tuple(dict.fromkeys(tuple(scene.PatternPieces) + tuple(selected))),
            key=lambda obj: str(obj.PieceId),
        )
        scene.PiecePlacements = [existing[key].to_string() for key in sorted(existing)]
        scene.HomePlacements = [homes[key].to_string() for key in sorted(homes)]

        payload = signature_payload(
            repr(source_signature(
                target.SourceObject,
                float(target.CollisionDeflection),
                float(target.CollisionThickness),
            )),
            [pid for _, pid, _, _, _, _ in plans],
            plans[0][2],
            clearance=float(clearance),
            max_translation=float(max_translation),
            max_rotation_degrees=float(max_rotation_degrees),
        )
        payload["profiles"] = {
            pid: {
                "primary_wrap_direction": profile.primary_wrap_direction,
                "anchors": tuple(
                    (
                        anchor.name,
                        tuple(float(value) for value in anchor.local_position),
                        anchor.wrap_direction,
                        float(anchor.weight),
                    )
                    for anchor in profile.anchors
                ),
            }
            for _, pid, profile, _, _, _ in plans
        }
        scene.TargetPlacementSignature = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        scene.TargetPlacementClearance = float(clearance)
        scene.DrapeTarget = target
        scene.FitStatus = "Target arranged"
        doc.recompute()
    except Exception:
        for piece in selected:
            piece.Placement = old_placements[str(piece.PieceId)]
        existing.clear()
        existing.update(old_piece_values)
        homes.clear()
        homes.update(old_home_values)
        scene.PiecePlacements = [existing[key].to_string() for key in sorted(existing)]
        scene.HomePlacements = [homes[key].to_string() for key in sorted(homes)]
        if hasattr(scene, "TargetPlacementSignature"):
            scene.TargetPlacementSignature = old_signature
        if hasattr(scene, "TargetPlacementClearance"):
            scene.TargetPlacementClearance = old_clearance
        doc.recompute()
        raise
    return scene


def create_arrangement_point(name, x, y, offset=0.0, wrap_direction="front", rotation_z=0.0, symmetry_group="", mirror=False):
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    point = ArrangementPoint(str(name), float(x), float(y), float(offset), str(wrap_direction), float(rotation_z), str(symmetry_group))
    point.validate()
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    values[point.name] = point
    if mirror:
        if not symmetry_group.strip():
            raise ValueError("mirror arrangement points require a symmetry group")
        mirrored = point.mirrored()
        values[mirrored.name] = mirrored
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    scene.SymmetryEnabled = bool(scene.SymmetryEnabled)
    _sync_visuals(scene)
    return point


def set_arrangement_point(name, x=None, y=None, offset=None, wrap_direction=None, rotation_z=None, symmetry_group=None):
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        raise ValueError("unknown arrangement point: %s" % name)
    old = values[name]
    point = ArrangementPoint(old.name, old.x if x is None else float(x), old.y if y is None else float(y),
                             old.offset if offset is None else float(offset), old.wrap_direction if wrap_direction is None else str(wrap_direction),
                             old.rotation_z if rotation_z is None else float(rotation_z), old.symmetry_group if symmetry_group is None else str(symmetry_group))
    point.validate()
    values[name] = point
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    doc.recompute()
    return point


def delete_arrangement_point(name):
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before deleting an arrangement point")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if name not in values:
        raise ValueError("unknown arrangement point: %s" % name)
    del values[name]
    scene.ArrangementPoints = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return scene


def create_bounding_volume(name, center=(0.0, 0.0, 0.0), size=(100.0, 100.0, 100.0)):
    from freecad_cloth.avatar.AvatarFitting import BoundingVolume
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc) or create_fitting_scene()
    volume = BoundingVolume(str(name), tuple(float(v) for v in center), tuple(float(v) for v in size))
    volume.validate()
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    values[volume.name] = volume
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return volume


def delete_bounding_volume(name):
    from freecad_cloth.avatar.AvatarFitting import BoundingVolume
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before deleting a bounding volume")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {v.name: v for v in (BoundingVolume.from_string(v) for v in scene.BoundingVolumes)}
    if name not in values:
        raise ValueError("unknown bounding volume: %s" % name)
    del values[name]
    scene.BoundingVolumes = [values[k].to_string() for k in sorted(values)]
    _sync_visuals(scene)
    return scene


def set_symmetry_enabled(enabled=True):
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before changing fitting symmetry")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    scene.SymmetryEnabled = bool(enabled)
    doc.recompute()
    return scene


def apply_arrangement_point(piece, point, mirror=None):
    """Place a pattern piece at a named point, optionally using its symmetric mate."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import ArrangementPoint
    if getattr(piece, "PatternType", "") != "PatternPiece":
        raise ValueError("piece must be a Cloth PatternPiece object")
    doc = App.ActiveDocument
    scene = _scene(doc) if doc else None
    if scene is None:
        raise ValueError("create a fitting scene first")
    values = {p.name: p for p in (ArrangementPoint.from_string(v) for v in scene.ArrangementPoints)}
    if isinstance(point, str):
        if point not in values:
            raise ValueError("unknown arrangement point: %s" % point)
        point = values[point]
    point.validate()
    if mirror is True and scene.SymmetryEnabled:
        point = point.mirrored()
    rotations = {"front": point.rotation_z, "back": point.rotation_z + 180.0, "left": point.rotation_z + 90.0, "right": point.rotation_z - 90.0}
    return position_piece(piece, point.x, point.y, point.offset, rotations[point.wrap_direction])


def reset_arrangement():
    """Restore every assigned piece to its saved pre-arrangement placement."""
    import FreeCAD as App
    from freecad_cloth.avatar.AvatarFitting import PiecePlacement
    doc = App.ActiveDocument
    if doc is None:
        raise ValueError("open a document before resetting arrangement")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    pieces = {str(p.PieceId): p for p in scene.PatternPieces}
    homes = {p.piece_id: p for p in (PiecePlacement.from_string(v) for v in scene.HomePlacements)}
    current = {}
    for pid, placement in homes.items():
        piece = pieces.get(pid)
        if piece is None:
            continue
        x, y, z = placement.position
        axis = App.Vector(*placement.rotation_axis)
        piece.Placement = App.Placement(App.Vector(x, y, z), App.Rotation(axis, placement.rotation_z))
        current[pid] = placement
    scene.PiecePlacements = [current[k].to_string() for k in sorted(current)]
    if hasattr(scene, "TargetPlacementSignature"):
        scene.TargetPlacementSignature = ""
    if hasattr(scene, "TargetPlacementClearance"):
        scene.TargetPlacementClearance = 0.0
    scene.FitStatus = "Arrangement reset"
    doc.recompute()
    return scene


def create_simulation_from_fitting():
    import FreeCAD as App
    doc = App.ActiveDocument or App.newDocument("ClothSewing")
    scene = _scene(doc)
    if scene is None:
        raise ValueError("create a fitting scene first")
    if not scene.PatternPieces:
        raise ValueError("add at least one pattern piece to the fitting scene")
    from freecad_cloth.simulation.SimulationObjects import create_simulation_scene
    simulation = create_simulation_scene(doc)
    simulation.ClothPieces = list(scene.PatternPieces)
    if scene.AvatarProxy is not None:
        simulation.AvatarProxy = scene.AvatarProxy
    if getattr(scene, "DrapeTarget", None) is not None:
        simulation.DrapeTarget = scene.DrapeTarget
    doc.recompute()
    return simulation


class _FittingProxy:
    Type = "ClothFittingScene"

    def execute(self, obj):
        from freecad_cloth.avatar.AvatarFitting import BodyMeasurements, FittingScene, PiecePlacement, ArrangementPoint, BoundingVolume
        _migrate_visual_output_references(obj)
        measurements = BodyMeasurements.from_json(obj.MeasurementData)
        avatar_name = getattr(obj.AvatarProxy, "Label", "") if obj.AvatarProxy else ""
        placements = tuple(PiecePlacement.from_string(v) for v in obj.PiecePlacements)
        points = tuple(ArrangementPoint.from_string(v) for v in obj.ArrangementPoints)
        volumes = tuple(BoundingVolume.from_string(v) for v in obj.BoundingVolumes)
        FittingScene(measurements, avatar_name, placements, points, volumes, bool(obj.SymmetryEnabled)).validate()
        target = getattr(obj, "DrapeTarget", None)
        if target is not None and str(getattr(target, "TargetType", "")) not in ("Mannequin", "FreeCAD Geometry"):
            raise ValueError("unsupported fitting DrapeTarget type")


COMMANDS = [
    "ClothFitting_CreateScene",
    "ClothFitting_SetMeasurements",
    "ClothFitting_AssignAvatar",
    "ClothFitting_AddPieces",
    "ClothFitting_CreateArrangementPoint",
    "ClothFitting_SetArrangementPoint",
    "ClothFitting_DeleteArrangementPoint",
    "ClothFitting_CreateBoundingVolume",
    "ClothFitting_DeleteBoundingVolume",
    "ClothFitting_SetSymmetry",
    "ClothFitting_ApplyArrangementPoint",
    "ClothFitting_SnapPiecesToTarget",
    "ClothFitting_ResetArrangement",
    "ClothFitting_CreateSimulation",
]
_COMMAND_HANDLERS = {
    "ClothFitting_CreateScene": create_fitting_scene,
    "ClothFitting_SetMeasurements": lambda: set_body_measurements({"height": 1700, "chest": 900, "waist": 760, "hip": 960, "shoulder": 420}),
    "ClothFitting_AssignAvatar": assign_avatar_source,
    "ClothFitting_AddPieces": add_selected_pattern_pieces,
    "ClothFitting_CreateArrangementPoint": lambda: create_arrangement_point("Point1", 0, 0),
    "ClothFitting_SetArrangementPoint": lambda: set_arrangement_point("Point1", x=0, y=0),
    "ClothFitting_DeleteArrangementPoint": lambda: delete_arrangement_point("Point1"),
    "ClothFitting_CreateBoundingVolume": lambda: create_bounding_volume("Volume1"),
    "ClothFitting_DeleteBoundingVolume": lambda: delete_bounding_volume("Volume1"),
    "ClothFitting_SetSymmetry": lambda: set_symmetry_enabled(True),
    "ClothFitting_ApplyArrangementPoint": lambda: _apply_selected_arrangement(),
    "ClothFitting_SnapPiecesToTarget": snap_pattern_pieces_to_target,
    "ClothFitting_ResetArrangement": reset_arrangement,
    "ClothFitting_CreateSimulation": create_simulation_from_fitting,
}


def _apply_selected_arrangement():
    import FreeCADGui as Gui
    scene = _scene(Gui.activeDocument().Document)
    if scene is None:
        raise ValueError("create a fitting scene first")
    piece = next((o for o in Gui.Selection.getSelection() if getattr(o, "PatternType", "") == "PatternPiece"), None)
    point = next((o for o in Gui.Selection.getSelection() if getattr(o, "FittingType", "") == "ArrangementPoint"), None)
    if piece is None or point is None:
        raise ValueError("select a pattern piece and an arrangement point")
    return apply_arrangement_point(piece, point.PointName)


try:
    import FreeCADGui as Gui
    from freecad_cloth.common.CommandAdapter import register_commands
    register_commands(Gui, _COMMAND_HANDLERS)
except (ImportError, AttributeError):
    pass
