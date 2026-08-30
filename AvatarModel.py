"""FreeCAD-independent parametric human mannequin model.

Anthropometric measurements are authoritative; geometry is a deterministic
visual/collision representation derived from them. A FreeCAD bridge can use
``generate_mesh`` without making this module depend on FreeCAD.
"""
from dataclasses import dataclass, field
import json
from math import cos, pi, sin

DEFAULT_MEASUREMENTS = {
    "height": 1750.0, "neck": 380.0, "shoulder": 440.0,
    "chest": 980.0, "underbust": 850.0, "waist": 820.0,
    "high_hip": 900.0, "hip": 1020.0, "upper_arm": 310.0,
    "elbow": 270.0, "wrist": 170.0, "thigh": 570.0,
    "knee": 390.0, "calf": 380.0, "ankle": 230.0,
    "inseam": 800.0, "torso": 450.0, "front_waist": 430.0,
    "back_waist": 440.0,
}
LIMITS = {
    "height": (1200, 2300), "neck": (250, 600), "shoulder": (250, 650),
    "chest": (600, 1600), "underbust": (550, 1450), "waist": (500, 1500),
    "high_hip": (600, 1550), "hip": (650, 1700), "upper_arm": (180, 550),
    "elbow": (160, 500), "wrist": (110, 300), "thigh": (300, 850),
    "knee": (250, 600), "calf": (250, 650), "ankle": (160, 350),
    "inseam": (500, 1100), "torso": (300, 650),
    "front_waist": (300, 650), "back_waist": (300, 650),
}

@dataclass(frozen=True)
class Pose:
    preset: str = "standing"
    left_arm_angle: float = 12.0
    right_arm_angle: float = 12.0
    left_elbow_angle: float = 0.0
    right_elbow_angle: float = 0.0
    VALID_PRESETS = ("standing", "sewing", "sitting")
    def validate(self):
        if self.preset not in self.VALID_PRESETS:
            raise ValueError("unsupported avatar pose: %s" % self.preset)

@dataclass(frozen=True)
class Landmark:
    name: str
    position: tuple

@dataclass(frozen=True)
class AvatarParameters:
    measurements: dict = field(default_factory=lambda: dict(DEFAULT_MEASUREMENTS))
    skin_offset: float = 3.0
    pose: Pose = field(default_factory=Pose)
    schema_version: int = 1
    def __post_init__(self):
        values = dict(DEFAULT_MEASUREMENTS)
        values.update({str(k): float(v) for k, v in self.measurements.items()})
        object.__setattr__(self, "measurements", values)
        self.validate()
    def validate(self):
        if self.schema_version != 1:
            raise ValueError("unsupported avatar schema version")
        missing = set(DEFAULT_MEASUREMENTS) - set(self.measurements)
        if missing:
            raise ValueError("missing avatar measurements: %s" % ", ".join(sorted(missing)))
        for name, (low, high) in LIMITS.items():
            value = float(self.measurements[name])
            if not low <= value <= high:
                raise ValueError("avatar measurement %s must be between %.0f and %.0f mm" % (name, low, high))
        if self.measurements["underbust"] > self.measurements["chest"]:
            raise ValueError("underbust circumference cannot exceed chest circumference")
        if self.measurements["inseam"] >= self.measurements["height"]:
            raise ValueError("inseam must be shorter than height")
        if not 0 <= float(self.skin_offset) <= 50:
            raise ValueError("skin offset must be between 0 and 50 mm")
        self.pose.validate()
    def measurement(self, name):
        if name not in self.measurements:
            raise KeyError(name)
        return float(self.measurements[name])
    def with_measurements(self, **changes):
        values = dict(self.measurements)
        values.update({str(k): float(v) for k, v in changes.items()})
        return AvatarParameters(values, self.skin_offset, self.pose, self.schema_version)
    def to_json(self):
        self.validate()
        return json.dumps({"schema_version": self.schema_version, "units": "mm", "measurements": dict(sorted(self.measurements.items())), "skin_offset": float(self.skin_offset), "pose": {"preset": self.pose.preset, "left_arm_angle": self.pose.left_arm_angle, "right_arm_angle": self.pose.right_arm_angle, "left_elbow_angle": self.pose.left_elbow_angle, "right_elbow_angle": self.pose.right_elbow_angle}}, sort_keys=True, separators=(",", ":"))
    @classmethod
    def from_json(cls, payload):
        data = json.loads(str(payload))
        if data.get("units", "mm") != "mm":
            raise ValueError("avatar presets must use millimetres")
        p = data.get("pose", {})
        pose = Pose(str(p.get("preset", "standing")), float(p.get("left_arm_angle", 12)), float(p.get("right_arm_angle", 12)), float(p.get("left_elbow_angle", 0)), float(p.get("right_elbow_angle", 0)))
        return cls(data.get("measurements", {}), float(data.get("skin_offset", 3)), pose, int(data.get("schema_version", 1)))

def _ring(vertices, z, rx, ry, segments=24):
    start = len(vertices)
    for i in range(segments):
        a = 2 * pi * i / segments
        vertices.append((rx * cos(a), ry * sin(a), z))
    return start

def _connect(triangles, a, b, segments=24):
    for i in range(segments):
        j = (i + 1) % segments
        triangles.extend(((a + i, a + j, b + j), (a + i, b + j, b + i)))

def _ellipsoid(vertices, triangles, center, radii, rings=8, segments=24):
    cx, cy, cz = center; rx, ry, rz = radii; ids = []
    for r in range(rings + 1):
        phi = -pi / 2 + pi * r / rings
        ids.append(_ring(vertices, cz + rz * sin(phi), rx * cos(phi), ry * cos(phi), segments))
    for a, b in zip(ids, ids[1:]):
        _connect(triangles, a, b, segments)

def _capsule(vertices, triangles, a, b, radius, segments=16):
    ax, ay, az = a; bx, by, bz = b
    length = max(1.0, ((bx-ax)**2 + (by-ay)**2 + (bz-az)**2) ** 0.5)
    cx, cy, cz = ((ax+bx)/2, (ay+by)/2, (az+bz)/2)
    _ellipsoid(vertices, triangles, (cx, cy, cz), (radius, radius, length/2 + radius), 6, segments)

def _radii(circumference, depth_ratio=0.39, skin_offset=0.0):
    c = float(circumference); offset = float(skin_offset)
    return (max(1.0, c / (2 * pi) * 1.18) + offset, max(1.0, c * depth_ratio / pi) + offset)

def generate_mesh(params):
    """Return ``(vertices, triangles, landmarks)`` for the mannequin."""
    params.validate(); m = params.measurements; vertices, triangles = [], []
    chest_w, chest_d = _radii(m["chest"], skin_offset=params.skin_offset)
    waist_w, waist_d = _radii(m["waist"], .40, params.skin_offset)
    hip_w, hip_d = _radii(m["hip"], .42, params.skin_offset)
    pelvis_z = m["inseam"] + 120; waist_z = pelvis_z + m["back_waist"]
    chest_z = waist_z + max(90, m["torso"] * .72)
    shoulder_z = min(m["height"] - 180, chest_z + 150); neck_z = shoulder_z + 100
    rings = [_ring(vertices, pelvis_z-100, hip_w, hip_d), _ring(vertices, pelvis_z, hip_w*1.02, hip_d*1.02), _ring(vertices, waist_z, waist_w, waist_d), _ring(vertices, chest_z, chest_w, chest_d), _ring(vertices, shoulder_z, chest_w*.88, chest_d*.88), _ring(vertices, neck_z, m["neck"]/(2*pi) + params.skin_offset, m["neck"]/(2*pi)*.85 + params.skin_offset)]
    for a, b in zip(rings, rings[1:]): _connect(triangles, a, b)
    _capsule(vertices, triangles, (0, 0, neck_z-30), (0, 0, neck_z+70), m["neck"]/(2*pi)*.82 + params.skin_offset)
    _ellipsoid(vertices, triangles, (0, 0, neck_z+155), (m["neck"]/(2*pi)*1.22 + params.skin_offset, m["neck"]/(2*pi)*1.08 + params.skin_offset, 105 + params.skin_offset), 10, 24)
    shoulder_half = m["shoulder"] / 2; arm_radius = m["upper_arm"] / (2*pi) + params.skin_offset; wrist_radius = m["wrist"] / (2*pi) + params.skin_offset; arm_z = shoulder_z - 15
    for side in (-1, 1):
        sx = side * shoulder_half; ex = side * (shoulder_half + 125); wx = side * (shoulder_half + 245)
        _capsule(vertices, triangles, (sx, 0, arm_z), (ex, 0, arm_z-35), arm_radius)
        _capsule(vertices, triangles, (ex, 0, arm_z-35), (wx, 0, arm_z-55), max(wrist_radius*1.25, arm_radius*.72))
        _ellipsoid(vertices, triangles, (wx, 0, arm_z-65), (wrist_radius*1.15, wrist_radius, wrist_radius*2.2), 6, 16)
    knee_z = max(300, m["ankle"] + m["inseam"]*.52); ankle_z = m["ankle"] / 2
    thigh_radius = m["thigh"] / (2*pi) + params.skin_offset; calf_radius = m["calf"] / (2*pi) + params.skin_offset; hip_offset = hip_w * .42
    for side in (-1, 1):
        x = side * hip_offset
        _capsule(vertices, triangles, (x, 0, pelvis_z-20), (x, 0, knee_z), thigh_radius)
        _capsule(vertices, triangles, (x, 0, knee_z), (x, 0, ankle_z+55), calf_radius)
        _ellipsoid(vertices, triangles, (x, 35, ankle_z), (m["ankle"]/(2*pi)*1.6 + params.skin_offset, m["ankle"]/(2*pi)*2 + params.skin_offset, 45 + params.skin_offset), 6, 16)
    landmarks = {"neck": (0,0,neck_z), "chest": (0,0,chest_z), "underbust": (0,0,chest_z-75), "waist": (0,0,waist_z), "high_hip": (0,0,waist_z-70), "hip": (0,0,pelvis_z), "crotch": (0,0,pelvis_z-65), "shoulder_left": (-shoulder_half,0,arm_z), "shoulder_right": (shoulder_half,0,arm_z), "knee_left": (-hip_offset,0,knee_z), "knee_right": (hip_offset,0,knee_z), "ankle_left": (-hip_offset,0,ankle_z), "ankle_right": (hip_offset,0,ankle_z), "wrist_left": (-shoulder_half-245,0,arm_z-55), "wrist_right": (shoulder_half+245,0,arm_z-55)}
    return tuple(vertices), tuple(triangles), tuple(Landmark(k, tuple(map(float,p))) for k,p in sorted(landmarks.items()))
