# Copyright (C) 2026 FreeCAD Cloth contributors
"""FreeCAD-independent manual forward-kinematics posing for the mannequin.

The pose editor uses the pinned MakeHuman joint hierarchy and skinning weights.
User-authored rotations are persistent data; the deformed mesh remains a derived
representation rebuilt from that state.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, NotRequired, TypedDict

import numpy as np
from pydantic.dataclasses import dataclass as pydantic_dataclass

from freecad_cloth.avatar.SkeletonTypes import SkeletonData

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping


class JointRotationInput(TypedDict):
    """Dictionary input accepted by the persistent joint-rotation API."""

    bone: str
    x: NotRequired[float]
    y: NotRequired[float]
    z: NotRequired[float]


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


@pydantic_dataclass(frozen=True)
class JointRotation:
    """A persistent Euler rotation for one authored mannequin joint."""

    bone: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def validate(self) -> JointRotation:
        """Validate the joint name and bounded Euler angles."""
        if self.bone not in CONTROLLABLE_BONES:
            msg = f"unsupported mannequin joint: {self.bone}"
            raise ValueError(msg)
        for axis in ("x", "y", "z"):
            value = float(getattr(self, axis))
            if not -180.0 <= value <= 180.0:
                msg = f"{self.bone}.{axis} must be between -180 and 180 degrees"
                raise ValueError(msg)
        return self

    def mirrored(self) -> JointRotation:
        """Return the sagittal mirror of this joint rotation."""
        mirror = MIRROR_BONES.get(self.bone)
        if mirror is None:
            return self
        # X is left/right, Y is depth and Z is up in the Cloth mannequin space.
        # Reflecting a proper rotation across X=0 preserves the X rotation axis
        # and reverses the Y/Z rotation axes.
        return JointRotation(mirror, float(self.x), -float(self.y), -float(self.z))


def normalize_joint_rotations(
    rotations: Iterable[JointRotation | JointRotationInput] | None,
) -> tuple[JointRotation, ...]:
    """Validate, de-duplicate and deterministically order joint rotations."""
    values = {}
    for rotation in rotations or ():
        if isinstance(rotation, JointRotation):
            item = rotation
        elif isinstance(rotation, dict):
            item = JointRotation(**rotation)
        else:
            msg = "joint rotations must contain JointRotation or mapping values"
            raise TypeError(msg)
        item.validate()
        values[item.bone] = item
    return tuple(values[name] for name in CONTROLLABLE_BONES if name in values)


def joint_rotation_map(
    rotations: Iterable[JointRotation | JointRotationInput] | None,
) -> dict[str, JointRotation]:
    """Return joint rotations keyed by authored MakeHuman bone name."""
    return {item.bone: item for item in normalize_joint_rotations(rotations)}


def joint_rotations_to_json(
    rotations: Iterable[JointRotation | JointRotationInput] | None,
) -> str:
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


def joint_rotations_from_json(payload: str) -> tuple[JointRotation, ...]:
    """Deserialize the required versioned joint-pose JSON document.

    Args:
        payload: JSON encoded by joint_rotations_to_json.

    Returns:
        Validated joint rotations in canonical bone order.

    Raises:
        ValueError: If the payload is invalid JSON or uses an unsupported schema.
        TypeError: If the JSON root or joints member has the wrong type.
    """
    data = json.loads(payload)
    if not isinstance(data, dict):
        msg = "mannequin joint pose JSON must be an object"
        raise TypeError(msg)
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        msg = "unsupported mannequin joint-pose schema version"
        raise ValueError(msg)
    if data.get("units") != "deg":
        msg = "mannequin joint poses must use degrees"
        raise ValueError(msg)
    joints = data.get("joints")
    if not isinstance(joints, dict):
        msg = "mannequin joint pose JSON must contain a joints object"
        raise TypeError(msg)
    rotations = []
    for bone, values in joints.items():
        if not isinstance(values, dict):
            msg = f"joint pose for {bone} must be an object"
            raise TypeError(msg)
        rotations.append(
            JointRotation(
                str(bone),
                float(values.get("x", 0.0)),
                float(values.get("y", 0.0)),
                float(values.get("z", 0.0)),
            )
        )
    return normalize_joint_rotations(rotations)


def mirror_rotations(
    rotations: Iterable[JointRotation | JointRotationInput] | None,
) -> tuple[JointRotation, ...]:
    """Return a deterministic left/right mirrored pose."""
    mirrored = [item.mirrored() for item in normalize_joint_rotations(rotations)]
    return normalize_joint_rotations(mirrored)


Matrix = tuple[float, ...]
Vector = tuple[float, float, float]


@pydantic_dataclass(frozen=True)
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

    def inverse(self) -> AffineTransform:
        """Return the inverse of this rigid affine transform."""
        m = self.matrix
        inverse_matrix = (
            m[0],
            m[3],
            m[6],
            m[1],
            m[4],
            m[7],
            m[2],
            m[5],
            m[8],
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


def build_bone_transforms(
    source_vertices: tuple[Vector, ...],
    skeleton: SkeletonData,
    fit_point: Callable[[Vector], Vector],
    rotations: Iterable[JointRotation],
    rotation_pivots: Mapping[str, Vector] | None = None,
) -> dict[str, AffineTransform]:
    """Build FK transforms, using optional rig-defined pivots for driven bones."""
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
        rest_head = _joint_point(
            source_vertices, skeleton["joints"][bone["head"]], mapper=fit_point
        )
        rotation = rotation_map.get(bone_name)
        if rotation is None:
            local = IDENTITY
        else:
            pivot = (rotation_pivots or {}).get(bone_name, rest_head)
            local = _rotation_about_point(
                pivot,
                _rotation_matrix(rotation.x, rotation.y, rotation.z),
            )
        combined = _compose(parent_transform, local)
        cache[bone_name] = combined
        return combined

    for bone_name in skeleton["bones"]:
        visit(bone_name)
    return cache


def apply_weighted_fk(
    source_vertices: tuple[Vector, ...],
    rest_vertices: tuple[Vector, ...],
    skeleton: SkeletonData,
    weights: Mapping[str, tuple[tuple[int, float], ...]],
    fit_point: Callable[[Vector], Vector],
    rotations: Iterable[JointRotation],
    rotation_pivots: Mapping[str, Vector] | None = None,
) -> tuple[Vector, ...]:
    """Apply weighted FK using NumPy for vertex and skin-weight reductions.

    Bone transforms remain computed by the canonical hierarchy. Each bone's
    sparse vertex weights are then transformed and accumulated in array batches;
    unweighted vertices retain their rest coordinates and overfull weights are
    normalized exactly as in the original contract.

    Args:
        source_vertices: Source rig coordinates used to build joint transforms.
        rest_vertices: Fitted undeformed mesh coordinates.
        skeleton: Canonical source skeleton with joint memberships and parents.
        weights: Sparse per-bone skin weights as vertex-index/weight pairs.
        fit_point: Mapping from source coordinates to fitted coordinates.
        rotations: Authored rotations to apply in the shared forward-kinematics path.
        rotation_pivots: Optional explicit fitted-space rotation pivots per bone.

    Returns:
        The deformed vertex coordinates in original vertex-index order.
    """
    transforms = build_bone_transforms(
        source_vertices, skeleton, fit_point, rotations, rotation_pivots
    )
    rest = np.asarray(rest_vertices, dtype=np.float64).reshape((-1, 3))
    count = len(rest)
    accumulated = np.zeros((count, 3), dtype=np.float64)
    total_weights = np.zeros(count, dtype=np.float64)

    for bone_name, entries in weights.items():
        if not entries:
            continue
        sparse_entries = np.asarray(entries, dtype=np.float64).reshape((-1, 2))
        indices = sparse_entries[:, 0].astype(np.intp)
        values = np.where(sparse_entries[:, 1] > 0.0, sparse_entries[:, 1], 0.0)
        valid = (indices >= 0) & (indices < count) & (values > 0.0)
        if not bool(np.any(valid)):
            continue
        indices = indices[valid]
        values = values[valid]
        transform = transforms.get(bone_name, IDENTITY)
        matrix = np.asarray(transform.matrix, dtype=np.float64).reshape((3, 3))
        translation = np.asarray(transform.translation, dtype=np.float64)
        moved = rest[indices] @ matrix.T + translation
        np.add.at(accumulated, indices, moved * values[:, None])
        np.add.at(total_weights, indices, values)

    posed = rest.copy()
    normalize = total_weights > 1.0 + 1e-6
    blend = (total_weights > 1e-12) & ~normalize
    posed[normalize] = accumulated[normalize] / total_weights[normalize, None]
    posed[blend] = accumulated[blend] + (1.0 - total_weights[blend, None]) * rest[blend]
    return tuple((float(point[0]), float(point[1]), float(point[2])) for point in posed)
