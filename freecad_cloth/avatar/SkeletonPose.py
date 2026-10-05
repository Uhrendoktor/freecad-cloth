"""FreeCAD-independent manual forward-kinematics posing for the mannequin.

The pose editor uses the pinned MakeHuman joint hierarchy and skinning weights.
User-authored rotations are persistent data; the deformed mesh remains a derived
representation rebuilt from that state.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

CONTROLLABLE_JOINTS = (
    ("spine05", "Pelvis"),
    ("spine03", "Chest"),
    ("neck01", "Neck"),
    ("head", "Head"),
    ("clavicle.L", "Left clavicle"),
    ("upperarm01.L", "Left shoulder"),
    ("lowerarm01.L", "Left elbow"),
    ("wrist.L", "Left wrist"),
    ("clavicle.R", "Right clavicle"),
    ("upperarm01.R", "Right shoulder"),
    ("lowerarm01.R", "Right elbow"),
    ("wrist.R", "Right wrist"),
    ("upperleg01.L", "Left hip"),
    ("lowerleg01.L", "Left knee"),
    ("foot.L", "Left ankle"),
    ("upperleg01.R", "Right hip"),
    ("lowerleg01.R", "Right knee"),
    ("foot.R", "Right ankle"),
)

CONTROLLABLE_BONES = tuple(bone for bone, _label in CONTROLLABLE_JOINTS)
JOINT_LABELS = dict(CONTROLLABLE_JOINTS)
MIRROR_BONES = {
    "clavicle.L": "clavicle.R",
    "upperarm01.L": "upperarm01.R",
    "lowerarm01.L": "lowerarm01.R",
    "wrist.L": "wrist.R",
    "upperleg01.L": "upperleg01.R",
    "lowerleg01.L": "lowerleg01.R",
    "foot.L": "foot.R",
    "clavicle.R": "clavicle.L",
    "upperarm01.R": "upperarm01.L",
    "lowerarm01.R": "lowerarm01.L",
    "wrist.R": "wrist.L",
    "upperleg01.R": "upperleg01.L",
    "lowerleg01.R": "lowerleg01.L",
    "foot.R": "foot.L",
}


@dataclass(frozen=True)
class JointRotation:
    """A persistent Euler rotation for one authored mannequin joint."""

    bone: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def validate(self):
        """Validate the joint name and bounded Euler angles."""
        if self.bone not in CONTROLLABLE_BONES:
            raise ValueError(f"unsupported mannequin joint: {self.bone}")
        for axis in ("x", "y", "z"):
            value = float(getattr(self, axis))
            if not -180.0 <= value <= 180.0:
                raise ValueError(f"{self.bone}.{axis} must be between -180 and 180 degrees")
        return self

    def mirrored(self):
        """Return the sagittal mirror of this joint rotation."""
        mirror = MIRROR_BONES.get(self.bone)
        if mirror is None:
            return self
        # X is left/right, Y is depth and Z is up in the Cloth mannequin space.
        # Reflecting a proper rotation across X=0 preserves the X rotation axis
        # and reverses the Y/Z rotation axes.
        return JointRotation(mirror, float(self.x), -float(self.y), -float(self.z))


def normalize_joint_rotations(rotations) -> tuple[JointRotation, ...]:
    """Validate, de-duplicate and deterministically order joint rotations."""
    values = {}
    for rotation in rotations or ():
        if isinstance(rotation, JointRotation):
            item = rotation
        elif isinstance(rotation, dict):
            item = JointRotation(**rotation)
        else:
            raise TypeError("joint rotations must contain JointRotation or mapping values")
        item.validate()
        values[item.bone] = item
    return tuple(values[name] for name in CONTROLLABLE_BONES if name in values)


def joint_rotation_map(rotations) -> dict[str, JointRotation]:
    """Return joint rotations keyed by authored MakeHuman bone name."""
    return {item.bone: item for item in normalize_joint_rotations(rotations)}


def joint_rotations_to_json(rotations) -> str:
    """Serialize persistent joint rotations to deterministic JSON."""
    values = normalize_joint_rotations(rotations)
    return json.dumps(
        {
            "schema_version": 1,
            "units": "deg",
            "joints": {
                item.bone: {
                    "x": float(item.x),
                    "y": float(item.y),
                    "z": float(item.z),
                }
                for item in values
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def joint_rotations_from_json(payload) -> tuple[JointRotation, ...]:
    """Deserialize persistent joint rotations, accepting legacy empty values."""
    raw = str(payload or "").strip()
    if not raw:
        return ()
    data = json.loads(raw)
    if isinstance(data, dict) and "joints" in data:
        if data.get("schema_version", 1) != 1:
            raise ValueError("unsupported mannequin joint-pose schema version")
        if data.get("units", "deg") != "deg":
            raise ValueError("mannequin joint poses must use degrees")
        data = data["joints"]
    if not isinstance(data, dict):
        raise ValueError("mannequin joint pose JSON must contain a joints object")
    rotations = []
    for bone, values in data.items():
        if not isinstance(values, dict):
            raise ValueError(f"joint pose for {bone} must be an object")
        rotations.append(
            JointRotation(
                str(bone),
                float(values.get("x", 0.0)),
                float(values.get("y", 0.0)),
                float(values.get("z", 0.0)),
            )
        )
    return normalize_joint_rotations(rotations)


def mirror_rotations(rotations) -> tuple[JointRotation, ...]:
    """Return a deterministic left/right mirrored pose."""
    mirrored = []
    for item in normalize_joint_rotations(rotations):
        mirrored.append(item.mirrored())
    return normalize_joint_rotations(mirrored)


Matrix = tuple[float, ...]
Vector = tuple[float, float, float]


@dataclass(frozen=True)
class AffineTransform:
    """Small immutable affine transform used by the headless FK implementation."""

    matrix: Matrix
    translation: Vector

    def apply(self, point: Vector) -> Vector:
        """Transform one point."""
        x, y, z = point
        m = self.matrix
        t = self.translation
        return (
            m[0] * x + m[1] * y + m[2] * z + t[0],
            m[3] * x + m[4] * y + m[5] * z + t[1],
            m[6] * x + m[7] * y + m[8] * z + t[2],
        )

    def inverse(self) -> "AffineTransform":
        """Return the inverse of this rigid affine transform."""
        m = self.matrix
        inverse_matrix = (
            m[0], m[3], m[6],
            m[1], m[4], m[7],
            m[2], m[5], m[8],
        )
        tx, ty, tz = self.translation
        inverse_translation = (
            -(inverse_matrix[0] * tx + inverse_matrix[1] * ty + inverse_matrix[2] * tz),
            -(inverse_matrix[3] * tx + inverse_matrix[4] * ty + inverse_matrix[5] * tz),
            -(inverse_matrix[6] * tx + inverse_matrix[7] * ty + inverse_matrix[8] * tz),
        )
        return AffineTransform(inverse_matrix, inverse_translation)


IDENTITY = AffineTransform(
    (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    (0.0, 0.0, 0.0),
)


def _matmul(a: Matrix, b: Matrix) -> Matrix:
    """Multiply two row-major 3x3 matrices."""
    return tuple(
        sum(a[row * 3 + k] * b[k * 3 + col] for k in range(3))
        for row in range(3)
        for col in range(3)
    )


def _matvec(matrix: Matrix, vector: Vector) -> Vector:
    """Multiply a row-major matrix by a 3D vector."""
    x, y, z = vector
    return (
        matrix[0] * x + matrix[1] * y + matrix[2] * z,
        matrix[3] * x + matrix[4] * y + matrix[5] * z,
        matrix[6] * x + matrix[7] * y + matrix[8] * z,
    )


def _compose(first: AffineTransform, second: AffineTransform) -> AffineTransform:
    """Return the transform that applies second then first."""
    matrix = _matmul(first.matrix, second.matrix)
    translated = first.apply(second.translation)
    return AffineTransform(matrix, translated)


def _rotation_matrix(x_degrees: float, y_degrees: float, z_degrees: float) -> Matrix:
    """Return an XYZ Euler rotation matrix."""
    rx = math.radians(float(x_degrees))
    ry = math.radians(float(y_degrees))
    rz = math.radians(float(z_degrees))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = (1.0, 0.0, 0.0, 0.0, cx, -sx, 0.0, sx, cx)
    my = (cy, 0.0, sy, 0.0, 1.0, 0.0, -sy, 0.0, cy)
    mz = (cz, -sz, 0.0, sz, cz, 0.0, 0.0, 0.0, 1.0)
    return _matmul(mz, _matmul(my, mx))


def _rotation_about_point(point: Vector, rotation: Matrix) -> AffineTransform:
    """Create a rotation about an existing rest-space joint."""
    rotated = _matvec(rotation, point)
    return AffineTransform(rotation, tuple(point[i] - rotated[i] for i in range(3)))


def build_bone_transforms(source_vertices, skeleton, fit_point, rotations):
    """Build the FK transform for every authored skeleton bone."""
    from freecad_cloth.avatar.HumanoidMesh import _joint_point

    rotation_map = joint_rotation_map(rotations)
    cache = {}

    def visit(bone_name: str) -> AffineTransform:
        if bone_name in cache:
            return cache[bone_name]
        bone = skeleton["bones"].get(bone_name)
        if bone is None:
            cache[bone_name] = IDENTITY
            return IDENTITY
        parent_name = bone.get("parent")
        parent_transform = visit(parent_name) if parent_name else IDENTITY
        rest_head = fit_point(_joint_point(source_vertices, skeleton["joints"][bone["head"]]))
        rotation = rotation_map.get(bone_name)
        if rotation is None:
            local = IDENTITY
        else:
            local = _rotation_about_point(
                rest_head,
                _rotation_matrix(rotation.x, rotation.y, rotation.z),
            )
        combined = _compose(parent_transform, local)
        cache[bone_name] = combined
        return combined

    for bone_name in skeleton["bones"]:
        visit(bone_name)
    return cache


def apply_weighted_fk(source_vertices, rest_vertices, skeleton, weights, fit_point, rotations):
    """Apply weighted FK transforms to a fitted mesh using source skin weights."""
    transforms = build_bone_transforms(source_vertices, skeleton, fit_point, rotations)
    count = len(rest_vertices)
    accum = [[0.0, 0.0, 0.0] for _ in range(count)]
    weight_sum = [0.0] * count

    for bone_name, entries in weights.items():
        transform = transforms.get(bone_name, IDENTITY)
        for index, weight in entries:
            index = int(index)
            if not 0 <= index < count:
                continue
            value = max(0.0, float(weight))
            if value <= 0.0:
                continue
            px, py, pz = transform.apply(rest_vertices[index])
            accum[index][0] += value * px
            accum[index][1] += value * py
            accum[index][2] += value * pz
            weight_sum[index] += value

    posed = []
    for index, point in enumerate(rest_vertices):
        total = weight_sum[index]
        if total <= 1e-12:
            posed.append(tuple(float(v) for v in point))
            continue
        if total > 1.0 + 1e-6:
            scale = 1.0 / total
            posed.append(tuple(value * scale for value in accum[index]))
            continue
        residual = 1.0 - total
        posed.append(
            (
                accum[index][0] + residual * point[0],
                accum[index][1] + residual * point[1],
                accum[index][2] + residual * point[2],
            )
        )
    return tuple(posed)
