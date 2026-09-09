"""FreeCAD-independent parametric human avatar model.

Anthropometric measurements remain authoritative; geometry is now backed by the
real MakeHuman HM08 human base mesh and a deterministic measurement/pose fit.
"""
from dataclasses import dataclass, field
import json

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
        for name in ("left_arm_angle", "right_arm_angle", "left_elbow_angle", "right_elbow_angle"):
            value = float(getattr(self, name))
            if not -90.0 <= value <= 90.0:
                raise ValueError("%s must be between -90 and 90 degrees" % name)


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
        if not isinstance(self.pose, Pose):
            raise TypeError("pose must be a Pose")
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


def _landmarks(params):
    m = params.measurements
    height = float(m["height"])
    pelvis_z = min(height * 0.43, float(m["inseam"]) + 120.0)
    waist_z = min(height * 0.58, pelvis_z + float(m["back_waist"]))
    chest_z = min(height * 0.70, waist_z + max(90.0, float(m["torso"]) * 0.72))
    shoulder_z = min(height * 0.77, chest_z + 150.0)
    neck_z = min(height * 0.88, shoulder_z + 100.0)
    knee_z = max(300.0, float(m["ankle"]) + float(m["inseam"]) * 0.52)
    ankle_z = float(m["ankle"]) / 2.0
    shoulder_half = float(m["shoulder"]) / 2.0
    leg_x = max(55.0, float(m["hip"]) / (2.0 * 3.141592653589793) * 0.42)
    side_y = 230.0 if params.pose.preset == "sitting" else 0.0
    knees = {
        "left": (-leg_x, side_y, pelvis_z - 15.0) if params.pose.preset == "sitting" else (-leg_x, 0.0, knee_z),
        "right": (leg_x, side_y, pelvis_z - 15.0) if params.pose.preset == "sitting" else (leg_x, 0.0, knee_z),
    }
    arm_defaults = {"standing": 12.0, "sewing": 55.0, "sitting": 25.0}
    default = arm_defaults[params.pose.preset]
    wrists = {}
    for side, angle_value, elbow_value, label in ((-1.0, params.pose.left_arm_angle, params.pose.left_elbow_angle, "left"), (1.0, params.pose.right_arm_angle, params.pose.right_elbow_angle, "right")):
        angle = default if params.pose.preset != "standing" and angle_value == 12.0 else angle_value
        a = angle * 3.141592653589793 / 180.0
        ex = side * shoulder_half + side * 125.0 * __import__("math").cos(a)
        ez = shoulder_z - 125.0 * __import__("math").sin(a)
        fa = (angle - elbow_value) * 3.141592653589793 / 180.0
        wx = ex + side * 120.0 * __import__("math").cos(fa)
        wz = ez - 120.0 * __import__("math").sin(fa)
        wrists[label] = (wx, 0.0, wz)
    landmarks = {
        "neck": (0.0, 0.0, neck_z),
        "chest": (0.0, 0.0, chest_z),
        "underbust": (0.0, 0.0, chest_z - 75.0),
        "waist": (0.0, 0.0, waist_z),
        "high_hip": (0.0, 0.0, waist_z - 70.0),
        "hip": (0.0, 0.0, pelvis_z),
        "crotch": (0.0, 0.0, pelvis_z - 65.0),
        "shoulder_left": (-shoulder_half, 0.0, shoulder_z),
        "shoulder_right": (shoulder_half, 0.0, shoulder_z),
        "knee_left": knees["left"],
        "knee_right": knees["right"],
        "ankle_left": (-leg_x, side_y, ankle_z),
        "ankle_right": (leg_x, side_y, ankle_z),
        "wrist_left": wrists["left"],
        "wrist_right": wrists["right"],
    }
    return tuple(Landmark(name, tuple(map(float, position))) for name, position in sorted(landmarks.items()))


def generate_mesh(params):
    """Return ``(vertices, triangles, landmarks)`` from the real human mesh."""
    params.validate()
    from freecad_cloth.avatar.HumanoidMesh import build_humanoid_mesh
    mesh = build_humanoid_mesh(params)
    return mesh.vertices, mesh.triangles, _landmarks(params)
