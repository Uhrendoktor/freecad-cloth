"""FreeCAD-facing parametric human mannequin commands."""
from AvatarModel import AvatarParameters, DEFAULT_MEASUREMENTS, Pose
from AvatarArrangement import arrangement_points_from_landmarks

PROPERTY_MAP = {
    "height": "Height", "neck": "Neck", "shoulder": "Shoulder",
    "chest": "Chest", "underbust": "Underbust", "waist": "Waist",
    "high_hip": "High_Hip", "hip": "Hip", "upper_arm": "Upper_Arm",
    "elbow": "Elbow", "wrist": "Wrist", "thigh": "Thigh",
    "knee": "Knee", "calf": "Calf", "ankle": "Ankle",
    "inseam": "Inseam", "torso": "Torso", "front_waist": "Front_Waist",
    "back_waist": "Back_Waist",
}
POSE_PROPERTY_MAP = {
    "left_arm_angle": "LeftArmAngle", "right_arm_angle": "RightArmAngle",
    "left_elbow_angle": "LeftElbowAngle", "right_elbow_angle": "RightElbowAngle",
}


def _avatar(doc):
    return next((o for o in doc.Objects if getattr(o, "AvatarType", "") == "ClothAvatar"), None)


def _set_prop(obj, kind, name, group, value):
    if not hasattr(obj, name):
        obj.addProperty(kind, name, group)
    setattr(obj, name, value)


def _parameters(obj):
    values = {name: float(getattr(obj, PROPERTY_MAP[name])) for name in DEFAULT_MEASUREMENTS}
    pose = Pose(str(obj.PosePreset), *(float(getattr(obj, POSE_PROPERTY_MAP[name], 12.0 if "arm" in name else 0.0)) for name in ("left_arm_angle", "right_arm_angle", "left_elbow_angle", "right_elbow_angle")))
    return AvatarParameters(values, float(obj.SkinOffset), pose)


def _limb(base, end, radius):
    import FreeCAD as App, Part
    a, b = App.Vector(*base), App.Vector(*end)
    direction = b.sub(a)
    if direction.Length < 1e-6:
        return Part.makeSphere(radius, a)
    return Part.makeCylinder(radius, direction.Length, a, direction)


def _rebuild(obj):
    import FreeCAD as App, Part
    p = _parameters(obj); m = p.measurements; h = m["height"]; pi = 3.141592653589793
    chest_r = m["chest"]/(2*pi)*1.18+p.skin_offset; waist_r = m["waist"]/(2*pi)*1.18+p.skin_offset; hip_r = m["hip"]/(2*pi)*1.18+p.skin_offset; neck_r = m["neck"]/(2*pi)+p.skin_offset
    pelvis_z = m["inseam"]+120.0; waist_z = pelvis_z+m["back_waist"]; chest_z = waist_z+max(90.0,m["torso"]*.72); shoulder_z = min(h-180.0,chest_z+150.0); neck_z = shoulder_z+100.0
    shape = Part.makeCone(hip_r, waist_r, max(100.0,waist_z-pelvis_z), App.Vector(0,0,pelvis_z)).fuse(Part.makeCone(waist_r,chest_r,max(100.0,chest_z-waist_z),App.Vector(0,0,waist_z)))
    shape = shape.fuse(Part.makeCone(chest_r,chest_r*.88,150,App.Vector(0,0,chest_z))).fuse(Part.makeCylinder(neck_r,100,App.Vector(0,0,shoulder_z)))
    shape = shape.fuse(Part.makeSphere(max(70.0,h*.055)+p.skin_offset,App.Vector(0,0,neck_z+70)))
    knee_z=max(300.0,m["ankle"]+m["inseam"]*.52); ankle_z=m["ankle"]/2.0; leg_radius=max(28.0,m["thigh"]/(2*pi))+p.skin_offset; calf_radius=max(25.0,m["calf"]/(2*pi))+p.skin_offset; leg_x=max(55.0,hip_r*.42)
    for side in (-1.0,1.0):
        x=side*leg_x
        knee=(x,230.0,pelvis_z-15.0) if p.pose.preset=="sitting" else (x,0,knee_z)
        ankle=(x,230.0,ankle_z+55.0) if p.pose.preset=="sitting" else (x,0,ankle_z+55)
        for part in (_limb((x,0,pelvis_z),knee,leg_radius),_limb(knee,ankle,calf_radius),Part.makeSphere(max(35.0,m["ankle"]/(2*pi)),App.Vector(x,35,ankle_z)),Part.makeSphere(leg_radius*1.05,App.Vector(*knee))): shape=shape.fuse(part)
    shoulder_half=m["shoulder"]/2.0; arm_radius=max(22.0,m["upper_arm"]/(2*pi))+p.skin_offset; forearm_radius=max(20.0,m["elbow"]/(2*pi)*.9)+p.skin_offset; wrist_radius=max(16.0,m["wrist"]/(2*pi))+p.skin_offset; arm_z=shoulder_z-15
    defaults={"standing":12.0,"sewing":55.0,"sitting":25.0}
    wrists={}
    for side, arm_angle, elbow_angle, label in ((-1.0,p.pose.left_arm_angle,p.pose.left_elbow_angle,"left"),(1.0,p.pose.right_arm_angle,p.pose.right_elbow_angle,"right")):
        angle=defaults[p.pose.preset] if p.pose.preset!="standing" and arm_angle==12.0 else arm_angle
        a=angle*pi/180.0; sx=side*shoulder_half
        ex=sx+side*125.0*__import__('math').cos(a); ez=arm_z-125.0*__import__('math').sin(a)
        fa=(angle-elbow_angle)*pi/180.0; wx=ex+side*120.0*__import__('math').cos(fa); wz=ez-120.0*__import__('math').sin(fa)
        _capsule= lambda start,end,r: _limb(start,end,r)
        for part in (_capsule((sx,0,arm_z),(ex,0,ez),arm_radius),_capsule((ex,0,ez),(wx,0,wz),max(wrist_radius*1.25,arm_radius*.72)),Part.makeSphere(wrist_radius*1.25,App.Vector(wx,0,wz)),Part.makeSphere(arm_radius*1.1,App.Vector(sx,0,arm_z))): shape=shape.fuse(part)
        wrists[label]=(wx,0,wz)
    obj.Shape=shape; obj.ParametersJSON=p.to_json(); obj.AvatarStatus="Valid"
    obj.Landmarks=["neck|0,0,%.3f"%neck_z,"chest|0,0,%.3f"%chest_z,"waist|0,0,%.3f"%waist_z,"hip|0,0,%.3f"%pelvis_z,"shoulder_left|%.3f,0,%.3f"%(-shoulder_half,arm_z),"shoulder_right|%.3f,0,%.3f"%(shoulder_half,arm_z),"knee_left|%.3f,%.3f,%.3f"%tuple((-leg_x,230,pelvis_z-15) if p.pose.preset=="sitting" else (-leg_x,0,knee_z)),"knee_right|%.3f,%.3f,%.3f"%tuple((leg_x,230,pelvis_z-15) if p.pose.preset=="sitting" else (leg_x,0,knee_z)),"ankle_left|%.3f,%.3f,%.3f"%(-leg_x,230 if p.pose.preset=="sitting" else 0,ankle_z),"ankle_right|%.3f,%.3f,%.3f"%(leg_x,230 if p.pose.preset=="sitting" else 0,ankle_z),"wrist_left|%.3f,%.3f,%.3f"%wrists["left"],"wrist_right|%.3f,%.3f,%.3f"%wrists["right"]]
    _set_prop(obj, "App::PropertyStringList", "ArrangementPoints", "Fitting", [])
    obj.ArrangementPoints = arrangement_points_from_landmarks(obj.Landmarks)
    obj.Document.recompute()
    return obj


def _ensure_collision(obj):
    from SimulationObjects import set_avatar_collision_source
    avatar = obj.Document.getObject("AvatarCollision")
    if avatar is None:
        from SimulationObjects import create_avatar_collision
        avatar = create_avatar_collision(obj.Document, obj, thickness=2.0, deflection=1.0)
    else:
        avatar = set_avatar_collision_source(next((s for s in obj.Document.Objects if getattr(s, "FittingType", "") == "FittingScene"), None) or _make_scene(obj.Document), obj, 2.0, 1.0)
    return avatar


def _ensure_drape_target(obj):
    """Attach the mannequin to the same target-neutral collision API as CAD targets."""
    from DrapeTarget import assign_drape_target, create_drape_target
    target = obj.Document.getObject("DrapeTarget")
    if target is None:
        target = create_drape_target(obj.Document, target_type="Mannequin", deflection=1.0, thickness=2.0)
    assign_drape_target(target, obj, "Mannequin")
    return target


def _make_scene(doc):
    from FittingCommands import create_fitting_scene
    return create_fitting_scene()


def create_avatar():
    import FreeCAD as App
    doc=App.ActiveDocument or App.newDocument("ClothSewing")
    obj=_avatar(doc)
    if obj is None:
        obj=doc.addObject("Part::Feature","ClothAvatar"); obj.Label="Cloth Human Mannequin"
        _set_prop(obj,"App::PropertyString","AvatarType","Avatar","ClothAvatar"); _set_prop(obj,"App::PropertyString","SchemaVersion","Avatar","1")
        for name,value in DEFAULT_MEASUREMENTS.items(): _set_prop(obj,"App::PropertyLength",PROPERTY_MAP[name],"Measurements",value)
        _set_prop(obj,"App::PropertyLength","SkinOffset","Collision",3.0); _set_prop(obj,"App::PropertyEnumeration","PosePreset","Pose",["standing","sewing","sitting"]); obj.PosePreset="standing"
        for name, prop in POSE_PROPERTY_MAP.items(): _set_prop(obj,"App::PropertyAngle",prop,"Pose",12.0 if "arm" in name else 0.0)
        _set_prop(obj,"App::PropertyString","AvatarStatus","Avatar","Unbuilt"); _set_prop(obj,"App::PropertyString","ParametersJSON","Avatar",""); _set_prop(obj,"App::PropertyStringList","Landmarks","Measurements",[])
        _set_prop(obj,"App::PropertyStringList","ArrangementPoints","Fitting",[])
        _set_prop(obj,"App::PropertyLink","CollisionProxy","Collision",None)
        _set_prop(obj,"App::PropertyLink","DrapeTarget","Collision",None)
    else:
        for name, prop in POSE_PROPERTY_MAP.items(): _set_prop(obj,"App::PropertyAngle",prop,"Pose",12.0 if "arm" in name else 0.0)
    _rebuild(obj)
    collision = _ensure_collision(obj)
    target = _ensure_drape_target(obj)
    obj.CollisionProxy = collision
    obj.DrapeTarget = target
    doc.recompute()
    return obj


def rebuild_avatar():
    import FreeCAD as App
    doc=App.ActiveDocument
    if doc is None: raise ValueError("open a document before rebuilding the avatar")
    obj=_avatar(doc)
    if obj is None: raise ValueError("create a Cloth Avatar first")
    _rebuild(obj)
    obj.CollisionProxy = _ensure_collision(obj)
    obj.DrapeTarget = _ensure_drape_target(obj)
    return obj


def edit_avatar():
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("ClothSewing")
    obj = _avatar(doc) or create_avatar()
    from AvatarGui import show_avatar_task
    return show_avatar_task(obj)


def set_avatar_measurements(**changes):
    import FreeCAD as App
    doc=App.ActiveDocument
    if doc is None: raise ValueError("open a document before changing avatar measurements")
    obj=_avatar(doc) or create_avatar()
    allowed=set(DEFAULT_MEASUREMENTS)
    for name,value in changes.items():
        key=str(name)
        if key not in allowed: raise ValueError("unknown avatar measurement: %s"%name)
        setattr(obj,PROPERTY_MAP[key],float(value))
    return rebuild_avatar()


def set_avatar_pose(pose):
    import FreeCAD as App
    doc=App.ActiveDocument
    if doc is None: raise ValueError("open a document before changing avatar pose")
    obj=_avatar(doc) or create_avatar(); Pose(str(pose), float(getattr(obj,"LeftArmAngle",12)), float(getattr(obj,"RightArmAngle",12)), float(getattr(obj,"LeftElbowAngle",0)), float(getattr(obj,"RightElbowAngle",0))).validate(); obj.PosePreset=str(pose); return rebuild_avatar()


def set_avatar_skin_offset(offset):
    import FreeCAD as App
    doc=App.ActiveDocument
    if doc is None: raise ValueError("open a document before changing avatar offset")
    obj=_avatar(doc) or create_avatar(); obj.SkinOffset=float(offset); return rebuild_avatar()


def avatar_measurement(name):
    import FreeCAD as App
    doc=App.ActiveDocument
    if doc is None or _avatar(doc) is None: raise ValueError("create a Cloth Avatar first")
    return _parameters(_avatar(doc)).measurement(str(name))


def avatar_arrangement_points():
    """Return persisted local fitting points for the active mannequin."""
    import FreeCAD as App
    doc = App.ActiveDocument
    if doc is None or _avatar(doc) is None:
        raise ValueError("create a Cloth Avatar first")
    return arrangement_points_from_landmarks(_avatar(doc).Landmarks)


COMMANDS=["ClothFitting_CreateAvatar","ClothFitting_EditAvatar","ClothFitting_RebuildAvatar","ClothFitting_SetAvatarMeasurements","ClothFitting_SetAvatarPose","ClothFitting_SetAvatarSkinOffset"]
_HANDLERS={"ClothFitting_CreateAvatar":create_avatar,"ClothFitting_EditAvatar":edit_avatar,"ClothFitting_RebuildAvatar":rebuild_avatar,"ClothFitting_SetAvatarMeasurements":lambda:set_avatar_measurements(height=1750,chest=980,waist=820,hip=1020),"ClothFitting_SetAvatarPose":lambda:set_avatar_pose("sewing"),"ClothFitting_SetAvatarSkinOffset":lambda:set_avatar_skin_offset(5.0)}
try:
    import FreeCADGui as Gui
    from CommandAdapter import register_commands
    register_commands(Gui,_HANDLERS)
except (ImportError,AttributeError): pass
