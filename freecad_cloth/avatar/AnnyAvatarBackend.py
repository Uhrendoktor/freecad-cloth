"""Anny-backed avatar generation and measurement fitting.

Human shape generation and anthropometric fitting are delegated to Anny and
clad-body. A topology-preserving front-surface correction complements Anny's
vertical breast-volume target so Cloth's fullness control produces the expected
anterior projection on the visible avatar.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np

from freecad_cloth.avatar.HumanoidMesh import MAKEHUMAN_BODY_VERTEX_COUNT, MeshData

if TYPE_CHECKING:
    import torch

    from freecad_cloth.avatar.AvatarModel import AvatarParameters

# These are measurement keys implemented by clad-body's differentiable Anny
# measurement API. Fields without a corresponding library measurement remain
# stored in the document but are not used as false precision constraints here.
MEASUREMENT_FIELDS = (
    ("height", "height_cm"),
    ("chest", "bust_cm"),
    ("underbust", "underbust_cm"),
    ("waist", "waist_cm"),
    ("hip", "hip_cm"),
    ("thigh", "thigh_cm"),
    ("knee", "knee_cm"),
    ("calf", "calf_cm"),
    ("upper_arm", "upperarm_cm"),
    ("shoulder", "shoulder_width_cm"),
    ("inseam", "inseam_cm"),
    ("neck", "neck_cm"),
    ("sleeve_length", "sleeve_length_cm"),
)

# Measurement-specific target shapes provide controlled, local adjustments.
# Anny supplies the positive and negative shape directions for each label.
_LOCAL_CHANGE_TERMS = (
    "measure-bust-circ",
    "measure-underbust-circ",
    "measure-waist-circ",
    "measure-hips-circ",
    "measure-upperarm-circ",
    "measure-thigh-circ",
    "measure-knee-circ",
    "measure-calf-circ",
    "measure-neck-circ",
    "measure-sleeve-length",
    "measure-shoulder-dist",
    "torso-scale-horiz",
)
_BREAST_LOCAL_CHANGE = "breast-volume-vert-up"
# Cupsize and circumference are separate Cloth controls. Fitting bust and
# underbust back to the same target values can cancel or reverse the visible
# cupsize phenotype, so keep those measurements as user data, not shape-fit loss
# terms.
_BREAST_SHAPE_MEASUREMENT_FIELDS = frozenset({"chest", "underbust"})
_FIT_STEPS = max(1, int(os.environ.get("FREECAD_CLOTH_ANNY_FIT_STEPS", "40")))
_FIT_TOLERANCE = 0.012


def _configured_fit_steps() -> int:
    """Resolve the current fit-step budget from explicit runtime configuration."""
    return max(1, int(os.environ.get("FREECAD_CLOTH_ANNY_FIT_STEPS", str(_FIT_STEPS))))


class AnnyAvatarBackendError(RuntimeError):
    """Raised when Anny cannot produce a compatible avatar mesh."""


class _ForwardModel(Protocol):
    """Minimal writable model interface needed for the compatibility adapter."""

    forward: Callable[..., object]


class _AnnyCallableModel(Protocol):
    """Callable Anny model interface used by clad-body's dynamic return object."""

    def __call__(self, *args: object, **kwargs: object) -> dict[str, torch.Tensor]: ...


def _adapt_clad_body_pose_alias(model: object) -> None:
    """Translate clad-body 0.6.1 legacy forward calls for Anny 0.6."""
    forward = getattr(model, "forward", None)
    if not callable(forward):
        raise AnnyAvatarBackendError("Anny model does not expose a callable forward method.")
    original_forward: Callable[..., object] = forward

    def compatible_forward(*args: object, **kwargs: object) -> object:
        if kwargs.get("pose_parameterization") == "root_relative_world":
            kwargs["pose_parameterization"] = "local-bone"
        return original_forward(*args, **kwargs)

    # clad-body 0.6.1 still supplies root_relative_world on every forward call.
    # Anny 0.6 translates that alias only in the factory, not in forward().
    cast(_ForwardModel, model).forward = compatible_forward


@lru_cache(maxsize=1)
def _all_paired_local_change_labels() -> tuple[str, ...]:
    """Return discoverable paired Anny local-morph labels from every target group."""
    try:
        import anny
    except ImportError as exc:
        raise AnnyAvatarBackendError(
            "Anny is required for parametric mannequin generation; install "
            "'anny>=0.6,<0.7' and 'clad-body[anny]>=0.6.1,<0.7' in the FreeCAD Python environment."
        ) from exc

    package_file = getattr(anny, "__file__", None)
    if not package_file:
        raise AnnyAvatarBackendError("Unable to resolve the installed Anny package path.")
    root = Path(package_file).resolve().parent
    try:
        from anny.paths import get_anny_root_dir
    except ImportError:
        pass
    else:
        root = Path(get_anny_root_dir())
    metadata_path = root / "data" / "mpfb2" / "targets" / "target.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AnnyAvatarBackendError(
            f"Unable to read Anny morph-target metadata at {metadata_path}: {exc}"
        ) from exc

    selected: set[str] = set()
    for group_data in metadata.values():
        if not isinstance(group_data, dict):
            continue
        for category in group_data.get("categories", []):
            if not isinstance(category, dict):
                continue
            opposites = category.get("opposites", {})
            if not isinstance(opposites, dict):
                continue
            for side in ("left", "right", "unsided"):
                positive = opposites.get(f"positive-{side}", "")
                negative = opposites.get(f"negative-{side}", "")
                if (
                    isinstance(positive, str)
                    and positive
                    and isinstance(negative, str)
                    and negative
                ):
                    selected.add(positive)

    if _BREAST_LOCAL_CHANGE not in selected:
        raise AnnyAvatarBackendError(
            f"Anny assets do not provide the {_BREAST_LOCAL_CHANGE!r} shape control."
        )
    return tuple(sorted(selected))


def available_anny_local_change_labels() -> tuple[str, ...]:
    """Return every paired Anny local-morph parameter available in the installed assets."""
    return _all_paired_local_change_labels()


@lru_cache(maxsize=1)
def available_anny_phenotype_labels() -> tuple[str, ...]:
    """Ask the installed Anny API which normalized phenotype inputs it exposes."""
    try:
        import anny
    except ImportError as exc:
        raise AnnyAvatarBackendError(
            "Anny is required to inspect advanced mannequin parameters."
        ) from exc
    try:
        model = anny.create_fullbody_model(
            rig="default",
            topology="makehuman-tris",
            remove_unattached_vertices=False,
            triangulate_faces=True,
            pose_parameterization="local-bone",
            bone_orientation="blender-rootidentity",
            all_phenotypes=True,
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise AnnyAvatarBackendError(f"Unable to inspect Anny phenotype parameters: {exc}") from exc
    labels = getattr(model, "phenotype_labels", None)
    if labels is None:
        raise AnnyAvatarBackendError("The installed Anny model does not expose phenotype labels.")
    return tuple(sorted(str(label) for label in labels))


def default_anny_phenotype_values(
    gender: float = 0.5,
    breast_size: float = 0.0,
) -> dict[str, float]:
    """Return effective default values for every phenotype in this Anny model."""
    defaults = {
        "gender": 1.0 - float(gender),
        "age": 0.667,
        "muscle": 0.5,
        "weight": 0.5,
        "height": 0.5,
        "proportions": 0.5,
        "cupsize": float(breast_size),
        "firmness": 0.5,
        "african": 1.0 / 3.0,
        "asian": 1.0 / 3.0,
        "caucasian": 1.0 / 3.0,
    }
    return {name: float(defaults.get(name, 0.5)) for name in available_anny_phenotype_labels()}


@lru_cache(maxsize=1)
def _measurement_local_change_labels() -> tuple[str, ...]:
    """Return the local Anny morphs used by Cloth's anthropometric fit."""
    wanted = (*_LOCAL_CHANGE_TERMS, _BREAST_LOCAL_CHANGE)
    selected = tuple(
        label
        for label in _all_paired_local_change_labels()
        if any(term in label for term in wanted)
    )
    if _BREAST_LOCAL_CHANGE not in selected:
        raise AnnyAvatarBackendError(
            f"Anny assets do not provide the {_BREAST_LOCAL_CHANGE!r} shape control."
        )
    return selected


def _initial_phenotypes(
    gender: float,
    breast_size: float,
    phenotype_overrides: dict[str, float] | None = None,
    local_change_overrides: dict[str, float] | None = None,
) -> dict[str, float | dict[str, float]]:
    """Translate Cloth defaults and staged advanced overrides to Anny conventions."""
    phenotypes: dict[str, float | dict[str, float]] = {
        # Anny's gender endpoints are male=0 and female=1; Cloth uses the
        # inverse convention for its user-facing slider.
        "gender": 1.0 - gender,
        "age": 0.667,
        "muscle": 0.5,
        "weight": 0.5,
        "height": 0.5,
        "proportions": 0.5,
        "cupsize": breast_size,
        "firmness": 0.5,
        # Keep the unexposed race controls at Anny's neutral equal blend.
        "african": 1.0 / 3.0,
        "asian": 1.0 / 3.0,
        "caucasian": 1.0 / 3.0,
    }
    for name, value in (phenotype_overrides or {}).items():
        if name not in {"gender", "cupsize"}:
            phenotypes[str(name)] = float(value)

    local_values = dict.fromkeys(_measurement_local_change_labels(), 0.0)
    local_values.update(
        {str(name): float(value) for name, value in (local_change_overrides or {}).items()}
    )
    # Keep local breast fullness neutral while measurement fitting converges;
    # the primary Breast fullness control is applied after fitting.
    local_values[_BREAST_LOCAL_CHANGE] = 0.0
    phenotypes["_local_changes"] = local_values
    return phenotypes


def _smoothstep_weight(edge0: float, edge1: float, value: float) -> float:
    """Return a clamped cubic transition from zero to one."""
    factor = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return factor * factor * (3.0 - 2.0 * factor)


def _apply_front_breast_fullness(
    vertices: tuple[tuple[float, float, float], ...],
    breast_size: float,
    height_mm: float,
) -> tuple[tuple[float, float, float], ...]:
    """Add a smooth anterior projection to the visible chest vertices only.

    Anny's breast-volume-vert-up target primarily alters vertical fullness. The
    Cloth control also promises forward projection, so add a broad smooth Y offset
    in the canonical Z-up / +Y-anterior frame, limited to the chest and two lobes.
    """
    strength = max(0.0, min(1.0, float(breast_size)))
    if strength <= 0.0 or not math.isfinite(height_mm) or height_mm <= 0.0:
        return vertices

    adjusted: list[tuple[float, float, float]] = []
    for x_mm, y_mm, z_mm in vertices:
        normalized_z = z_mm / height_mm
        if 0.60 <= normalized_z <= 0.76 and abs(x_mm) < 190.0:
            front_weight = _smoothstep_weight(-18.0, 28.0, y_mm)
            vertical_weight = math.exp(-0.5 * ((normalized_z - 0.685) / 0.030) ** 2)
            lateral_weight = max(
                math.exp(-0.5 * ((x_mm - center_x) / 58.0) ** 2) for center_x in (-72.0, 72.0)
            )
            y_mm += 62.0 * strength * front_weight * vertical_weight * lateral_weight
        adjusted.append((x_mm, y_mm, z_mm))
    return tuple(adjusted)


def _canonicalize_anny_vertices(
    vertices: np.ndarray,
    reference_vertices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Normalize a fitted mesh using a stable reference body's origin.

    The hip-specific Anny morph can change the fitted mesh bounds. Re-centering
    from those post-fit bounds translates unrelated head/shoulder vertices, so
    derive the up axis, floor, and XY origin from the pre-hip reference instead.
    """
    points = np.asarray(vertices, dtype=np.float32).copy()
    reference = np.asarray(reference_vertices, dtype=np.float32)
    if (
        points.ndim != 2
        or points.shape[1] != 3
        or reference.shape != points.shape
        or not points.shape[0]
    ):
        raise ValueError("Anny vertices and reference must have matching shape (N, 3)")
    if not bool(np.isfinite(points).all() and np.isfinite(reference).all()):
        raise ValueError("Anny vertices and reference must be finite")

    # Match clad-body's Y-up -> Z-up conversion, but make the choice using the
    # reference so a local hip morph cannot change the inferred orientation.
    if int(np.argmax(reference.max(axis=0) - reference.min(axis=0))) == 1:
        points = points[:, (0, 2, 1)].copy()
        points[:, 2] = -points[:, 2]
        reference = reference[:, (0, 2, 1)].copy()
        reference[:, 2] = -reference[:, 2]

    points[:, 2] -= reference[:, 2].min()
    center_xy = (reference[:, :2].max(axis=0) + reference[:, :2].min(axis=0)) / 2
    points[:, :2] -= center_xy
    return points, center_xy


def _localize_hip_fit_delta(
    reference_vertices: np.ndarray,
    fitted_vertices: np.ndarray,
) -> np.ndarray:
    """Apply the fitted hip morph only across the hip/pelvis region.

    Anny's hip circumference target can leave small blendshape deltas outside the
    intended region. Keep the reference mesh exact above the pelvis and through
    the lower legs, with a smooth fade into the circumference-control band.
    Inputs must already share the same canonical reference coordinate frame.
    """
    reference = np.asarray(reference_vertices, dtype=np.float64)
    fitted = np.asarray(fitted_vertices, dtype=np.float64)
    if (
        reference.ndim != 2
        or reference.shape[1] != 3
        or fitted.shape != reference.shape
        or not len(reference)
    ):
        raise ValueError("Anny hip-fit vertices must have matching shape (N, 3)")
    if not bool(np.isfinite(reference).all() and np.isfinite(fitted).all()):
        raise ValueError("Anny hip-fit vertices must be finite")
    height = float(np.ptp(reference[:, 2]))
    if not math.isfinite(height) or height <= 0.0:
        raise ValueError("Anny hip-fit reference must have a positive vertical extent")

    normalized_z = (reference[:, 2] - float(reference[:, 2].min())) / height

    def smoothstep(edge0: float, edge1: float) -> np.ndarray:
        factor = np.clip((normalized_z - edge0) / (edge1 - edge0), 0.0, 1.0)
        return factor * factor * (3.0 - 2.0 * factor)

    hip_band = smoothstep(0.36, 0.44) * (1.0 - smoothstep(0.54, 0.64))
    return reference + (fitted - reference) * hip_band[:, None]


def _clad_measurement_targets(
    values: dict[str, float],
    mass_target_kg: float | None,
) -> tuple[tuple[str, str, float], ...]:
    """Build stable target values with explicit clad-body unit conversions."""
    targets = tuple(
        (parameter_name, key, float(values[parameter_name]) / 10.0)
        for parameter_name, key in MEASUREMENT_FIELDS
    )
    if mass_target_kg is not None:
        targets += (("mass_target_kg", "mass_kg", float(mass_target_kg)),)
    return targets


def _split_clad_targets(
    targets: tuple[tuple[str, str, float], ...],
) -> tuple[tuple[tuple[str, str, float], ...], tuple[tuple[str, str, float], ...]]:
    """Keep global silhouette targets separate from localized measurements.

    Sleeve length uses a local arm morph. Feeding it into the global phenotype
    optimizer lets it trade off against height and can produce an over-tall body.
    """
    global_targets = tuple(
        target
        for target in targets
        if target[0] not in {"hip", "sleeve_length"}
        and target[0] not in _BREAST_SHAPE_MEASUREMENT_FIELDS
    )
    local_targets = tuple(
        target for target in targets if target[0] not in {"height", "inseam", "mass_target_kg"}
    )
    return global_targets, local_targets


def _fit_anny_body(
    measurements: tuple[tuple[str, float], ...],
    gender: float,
    breast_size: float,
    phenotype_overrides: tuple[tuple[str, float], ...],
    local_change_overrides: tuple[tuple[str, float], ...],
    mass_target_kg: float | None,
    *,
    fit_hip: bool,
    fit_steps: int | None = None,
) -> tuple[MeshData, tuple[tuple[float, float, float], ...]]:
    """Fit an Anny body and preserve every indexed vertex for rig anchors."""
    fit_steps = _configured_fit_steps() if fit_steps is None else max(1, int(fit_steps))
    try:
        import anny
        import torch
        from clad_body.load.anny import build_anny_apose, load_anny_from_verts
        from clad_body.measure import measure_grad
    except ImportError as exc:
        raise AnnyAvatarBackendError(
            "Anny-backed mannequin generation requires 'anny>=0.6,<0.7' and 'clad-body[anny]>=0.6.1,<0.7'. "
            "Run `python -m pip install 'anny>=0.6,<0.7' 'clad-body[anny]>=0.6.1,<0.7'` with the Python interpreter used by FreeCAD."
        ) from exc

    values = dict(measurements)
    phenotype_override_values = dict(phenotype_overrides)
    local_override_values = dict(local_change_overrides)
    initial_parameters = _initial_phenotypes(
        gender, breast_size, phenotype_override_values, local_override_values
    )
    local_values = initial_parameters.pop("_local_changes")
    if not isinstance(local_values, dict):
        raise AnnyAvatarBackendError("Anny local-change parameters were not resolved.")
    phenotype_values = {
        name: float(value)
        for name, value in initial_parameters.items()
        if isinstance(value, (int, float))
    }
    # Fit circumference morphs against the neutral bust before applying the
    # independent cupsize phenotype. Otherwise the optimizer can absorb the
    # visible cupsize change while trying to match the same circumference targets.
    phenotype_values["cupsize"] = 0.0

    # Use Anny's compatibility factory, also used by clad-body's loader.
    # "makehuman" disables Anny's nudity edits; retaining unattached vertices
    # preserves the source HM08 vertex indices used by Cloth's saved rig/weights.
    model = anny.create_fullbody_model(
        rig="default",
        topology="makehuman-tris",
        local_changes=sorted(local_values),
        remove_unattached_vertices=False,
        triangulate_faces=True,
        pose_parameterization="local-bone",
        bone_orientation="blender-rootidentity",
        all_phenotypes=True,
    ).to(dtype=torch.float32, device="cpu")
    _adapt_clad_body_pose_alias(model)

    # Cloth's skin weights and authored joints index the unedited HM08 mesh.
    # Do not silently fit against a reordered/filtered topology.
    base_mesh_vertex_indices = getattr(model, "base_mesh_vertex_indices", None)
    if base_mesh_vertex_indices is None:
        raise AnnyAvatarBackendError(
            "The installed Anny model does not expose its base-mesh vertex index map."
        )
    base_ids = base_mesh_vertex_indices.detach().cpu().tolist()
    if base_ids[:MAKEHUMAN_BODY_VERTEX_COUNT] != list(range(MAKEHUMAN_BODY_VERTEX_COUNT)):
        raise AnnyAvatarBackendError(
            "Anny's selected topology does not preserve HM08 body vertex index order "
            "required by Cloth's saved skeleton and skinning weights."
        )

    missing_local_changes = set(local_values) - set(model.local_change_labels)
    if missing_local_changes:
        raise AnnyAvatarBackendError(
            "Anny is missing configured measurement morphs: "
            + ", ".join(sorted(missing_local_changes))
        )

    # Anny releases can expose additional phenotype controls. Every normalized
    # input starts neutral unless Cloth has an explicit default or saved override.
    phenotype_values = {str(name): 0.5 for name in model.phenotype_labels} | phenotype_values
    unknown_phenotypes = set(phenotype_override_values) - set(model.phenotype_labels)
    if unknown_phenotypes:
        raise AnnyAvatarBackendError(
            "Saved Anny phenotype overrides are unavailable in this model: "
            + ", ".join(sorted(unknown_phenotypes))
        )
    unknown_local_changes = set(local_override_values) - set(model.local_change_labels)
    if unknown_local_changes:
        raise AnnyAvatarBackendError(
            "Saved Anny morph overrides are unavailable in this model: "
            + ", ".join(sorted(unknown_local_changes))
        )
    phenotype_kwargs = {
        name: torch.tensor(
            [phenotype_values[name]], dtype=torch.float32, device="cpu", requires_grad=True
        )
        for name in model.phenotype_labels
    }

    local_kwargs = {
        name: torch.tensor(
            [float(local_values.get(name, 0.0))],
            dtype=torch.float32,
            device="cpu",
            requires_grad=True,
        )
        for name in model.local_change_labels
    }
    device = torch.device("cpu")
    pose = build_anny_apose(model, device)
    with torch.no_grad():
        initial_output = model(
            pose_parameters=pose,
            phenotype_kwargs=phenotype_kwargs,
            local_changes_kwargs=local_kwargs,
            pose_parameterization="local-bone",
            return_bone_ends=True,
        )
    height_m = float(values["height"]) / 1000.0

    def _canonical_points(vertex_tensor: torch.Tensor) -> torch.Tensor:
        points = vertex_tensor[0].detach().clone()
        extents = points.amax(dim=0) - points.amin(dim=0)
        if int(torch.argmax(extents).item()) == 1:
            # Match clad-body.load_anny_from_verts: raw Anny tensors are Y-up,
            # while avatar mesh diagnostics use the canonical Z-up/+Y-front frame.
            points = points[:, (0, 2, 1)].clone()
            points[:, 2] = -points[:, 2]
        points[:, 2] -= points[:, 2].amin()
        center_xy = (points[:, :2].amax(dim=0) + points[:, :2].amin(dim=0)) / 2
        points[:, :2] -= center_xy
        return points

    def _front_y_mm(vertex_tensor: torch.Tensor) -> dict[str, float | None]:
        points = _canonical_points(vertex_tensor)
        result = {}
        for side, label in ((-1.0, "left"), (1.0, "right")):
            mask = (
                (points[:, 2] >= 0.64 * height_m)
                & (points[:, 2] <= 0.73 * height_m)
                & (points[:, 1] > 0.0)
                & (side * points[:, 0] >= 0.025)
                & (side * points[:, 0] <= 0.155)
            )
            result[label] = (
                float(points[mask, 1].max().item() * 1000.0) if bool(mask.any()) else None
            )
        return result

    def _write_shape_trace(stage: str, payload: dict[str, object]) -> None:
        if os.environ.get("CLOTH_ANNY_SHAPE_TRACE") != "1":
            return
        trace_path = Path("artifacts") / "anny-shape-trace.log"
        try:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"stage": stage, **payload}, sort_keys=True) + "\n")
        except OSError as exc:
            print("anny-shape-trace-write-failed %r" % (exc,), flush=True)

    if os.environ.get("CLOTH_ANNY_SHAPE_TRACE") == "1":
        raw_front_y = _front_y_mm(initial_output["vertices"])
        breast_labels = [
            str(label)
            for label in getattr(model, "blendshape_labels", ())
            if str(label).startswith("breast:")
        ]
        try:
            from anny.paths import get_anny_root_dir

            breast_asset_dir = Path(get_anny_root_dir()) / "data" / "mpfb2" / "targets" / "breast"
            breast_asset_count = len(tuple(breast_asset_dir.glob("*.target.gz")))
        except (ImportError, OSError, RuntimeError):
            breast_asset_count = None
        _write_shape_trace(
            "pre-fit",
            {
                "gender": phenotype_values["gender"],
                "cupsize": phenotype_values["cupsize"],
                "front_lobe_y_mm": raw_front_y,
                "cupsize_phenotype_enabled": "cupsize" in getattr(model, "phenotype_labels", ()),
                "breast_blendshape_count": len(breast_labels),
                "breast_blendshape_examples": breast_labels[:4],
                "breast_asset_file_count": breast_asset_count,
            },
        )
        print(
            "anny-shape-trace stage=pre-fit gender=%s cupsize=%s front_lobe_y_mm=%r "
            "cupsize_enabled=%s breast_blendshapes=%d breast_assets=%r"
            % (
                phenotype_values["gender"],
                phenotype_values["cupsize"],
                raw_front_y,
                "cupsize" in getattr(model, "phenotype_labels", ()),
                len(breast_labels),
                breast_asset_count,
            ),
            flush=True,
        )

    body = load_anny_from_verts(
        initial_output["vertices"],
        model,
        phenotype_kwargs=phenotype_kwargs,
        local_changes_kwargs=local_kwargs,
        bone_heads=initial_output.get("bone_heads"),
        bone_tails=initial_output.get("bone_tails"),
        source="FreeCAD Cloth / Anny",
    )

    targets = tuple(
        (parameter_name, key, float(values[parameter_name]) / 10.0)
        for parameter_name, key in MEASUREMENT_FIELDS
    )
    if mass_target_kg is not None:
        targets += (("mass_target_kg", "mass_kg", float(mass_target_kg)),)
    # Keep hip and sleeve-only targets out of the global phenotype fit. Sleeve
    # length is constrained later with its local arm morph to preserve body height.
    global_targets, local_targets = _split_clad_targets(targets)
    if body.phenotype_kwargs is None or body.local_changes_kwargs is None:
        raise AnnyAvatarBackendError("Anny did not expose trainable phenotype/local-change inputs.")
    global_phenotype_names = {"height", "weight", "muscle", "proportions"}
    missing_global_phenotypes = global_phenotype_names - set(body.phenotype_kwargs)
    if missing_global_phenotypes:
        raise AnnyAvatarBackendError(
            "Anny is missing the global fit controls: "
            + ", ".join(sorted(missing_global_phenotypes))
        )
    if not global_targets or not local_targets:
        raise AnnyAvatarBackendError("Anny measurement fitting has an empty target group.")

    # Hold the non-hip measurement target set fixed so hip edits cannot bias
    # the global controls that determine head, neck, shoulder and arm positions.
    initial_global_values = {
        name: body.phenotype_kwargs[name].detach().clone() for name in global_phenotype_names
    }
    global_parameters = [
        value for name, value in body.phenotype_kwargs.items() if name in global_phenotype_names
    ]
    for name, value in body.phenotype_kwargs.items():
        value.requires_grad_(name in global_phenotype_names)
    for value in body.local_changes_kwargs.values():
        value.requires_grad_(False)

    global_optimizer = torch.optim.Adam(global_parameters, lr=0.035)
    global_target_keys = [key for _name, key, _target in global_targets]
    global_target_values = {
        key: torch.tensor(target, dtype=torch.float32) for _name, key, target in global_targets
    }
    for _step in range(fit_steps):
        global_optimizer.zero_grad(set_to_none=True)
        actual = measure_grad(body, only=global_target_keys)
        relative_errors = [
            (actual[key] - global_target_values[key]).abs()
            / global_target_values[key].clamp_min(1.0)
            for _name, key, _target in global_targets
        ]
        if float(torch.stack(relative_errors).max().detach()) <= _FIT_TOLERANCE:
            break
        measurement_loss = torch.stack(
            [
                (
                    (actual[key] - global_target_values[key])
                    / global_target_values[key].clamp_min(1.0)
                )
                ** 2
                for _name, key, _target in global_targets
            ]
        ).mean()
        phenotype_penalty = torch.stack(
            [
                (body.phenotype_kwargs[name] - initial_global_values[name]).square().mean()
                for name in global_phenotype_names
            ]
        ).sum()
        loss = measurement_loss + 0.002 * phenotype_penalty
        loss.backward()
        global_optimizer.step()
        with torch.no_grad():
            for name in global_phenotype_names:
                body.phenotype_kwargs[name].clamp_(0.0, 1.0)

    if os.environ.get("CLOTH_ANNY_SHAPE_TRACE") == "1":
        with torch.no_grad():
            global_output = cast(_AnnyCallableModel, body.model)(
                pose_parameters=pose,
                phenotype_kwargs=body.phenotype_kwargs,
                local_changes_kwargs=body.local_changes_kwargs,
                pose_parameterization="local-bone",
                return_bone_ends=True,
            )
        _write_shape_trace(
            "post-global-fit",
            {
                "gender": float(body.phenotype_kwargs["gender"].detach().item()),
                "cupsize": float(body.phenotype_kwargs["cupsize"].detach().item()),
                "front_lobe_y_mm": _front_y_mm(global_output["vertices"]),
                "bust_morphs": {
                    name: float(value.detach().reshape(-1)[0].item())
                    for name, value in body.local_changes_kwargs.items()
                    if "bust" in name or "underbust" in name
                },
            },
        )

    # Freeze global phenotypes and fit the local measurement morphs separately.
    # This keeps local circumference requests from being "solved" by changing
    # body height, weight, muscle, or overall proportions.
    for value in body.phenotype_kwargs.values():
        value.requires_grad_(False)

    breast_names = {_BREAST_LOCAL_CHANGE}
    hip_change_names = {name for name in body.local_changes_kwargs if "measure-hips-circ" in name}
    if not hip_change_names:
        raise AnnyAvatarBackendError("Anny exposes no hip-specific circumference morphs.")
    non_hip_targets = tuple(target for target in local_targets if target[0] != "hip")
    hip_targets = tuple(target for target in local_targets if target[0] == "hip")
    if len(hip_targets) != 1 or not non_hip_targets:
        raise AnnyAvatarBackendError(
            "Anny local measurement targets cannot be separated by region."
        )

    # Fit every non-hip dimension without allowing the hip morph to pull the
    # torso/neck/shoulder controls. This makes hip-only edits spatially local.
    local_parameters = []
    for name, value in body.local_changes_kwargs.items():
        trainable = name not in breast_names and name not in hip_change_names
        value.requires_grad_(trainable)
        if trainable:
            local_parameters.append(value)
    if not local_parameters:
        raise AnnyAvatarBackendError("Anny exposes no trainable non-hip measurement morphs.")

    local_optimizer = torch.optim.Adam(local_parameters, lr=0.035)
    local_target_keys = [key for _name, key, _target in non_hip_targets]
    local_target_values = {
        key: torch.tensor(target, dtype=torch.float32) for _name, key, target in non_hip_targets
    }
    for _step in range(fit_steps):
        local_optimizer.zero_grad(set_to_none=True)
        actual = measure_grad(body, only=local_target_keys)
        relative_errors = [
            (actual[key] - local_target_values[key]).abs() / local_target_values[key].clamp_min(1.0)
            for _name, key, _target in non_hip_targets
        ]
        if float(torch.stack(relative_errors).max().detach()) <= _FIT_TOLERANCE:
            break
        measurement_loss = torch.stack(
            [
                ((actual[key] - local_target_values[key]) / local_target_values[key].clamp_min(1.0))
                ** 2
                for _name, key, _target in non_hip_targets
            ]
        ).mean()
        local_penalties = [
            value.square().mean()
            for name, value in body.local_changes_kwargs.items()
            if name not in breast_names and name not in hip_change_names
        ]
        local_penalty = torch.stack(local_penalties).mean()
        loss = measurement_loss + 0.0005 * local_penalty
        loss.backward()
        local_optimizer.step()
        with torch.no_grad():
            for name, value in body.local_changes_kwargs.items():
                if name not in breast_names and name not in hip_change_names:
                    value.clamp_(-1.0, 1.0)

    model = cast(_AnnyCallableModel, body.model)
    if body.phenotype_kwargs is None:
        raise AnnyAvatarBackendError("Anny did not preserve the fitted phenotype tensors.")
    if body.local_changes_kwargs is None:
        raise AnnyAvatarBackendError("Anny did not preserve the fitted morph tensors.")
    cupsize_control = body.phenotype_kwargs.get("cupsize")
    if cupsize_control is None:
        raise AnnyAvatarBackendError("Anny did not expose its independent cupsize phenotype.")
    breast_volume_control = body.local_changes_kwargs.get(_BREAST_LOCAL_CHANGE)
    if breast_volume_control is None:
        raise AnnyAvatarBackendError("Anny did not expose its breast-volume shape target.")
    # Cupsize provides the parametric phenotype; the localized volume target makes
    # that edit visible on the rig-compatible HM08 surface. Apply both after fitting
    # so the anthropometry optimizer cannot absorb the requested fullness.
    with torch.no_grad():
        # Advanced inputs are deliberately applied after the anthropometric fit:
        # setting a phenotype/morph is authoritative for that control, even when
        # it means its resulting measurement differs from the requested target.
        for name, value in phenotype_override_values.items():
            body.phenotype_kwargs[name].fill_(float(value))
        for name, value in local_override_values.items():
            body.local_changes_kwargs[name].fill_(float(value))
        cupsize_control.fill_(float(breast_size))
        breast_volume_control.fill_(float(breast_size))
    first_parameter = next(iter(body.phenotype_kwargs.values()))
    pose = build_anny_apose(model, first_parameter.device)
    rig_vertices: tuple[tuple[float, float, float], ...] | None = None
    canonical_reference_vertices: np.ndarray | None = None
    if fit_hip:
        # Capture the rig's neutral hip shape before fitting the hip-only morph.
        # This snapshot lets rig anchors and the visible mesh share one Anny fit.
        with torch.no_grad():
            rig_output = model(
                pose_parameters=pose,
                phenotype_kwargs=body.phenotype_kwargs,
                local_changes_kwargs=body.local_changes_kwargs,
                pose_parameterization="local-bone",
                return_bone_ends=True,
            )
        rig_output_vertices = rig_output["vertices"]
        canonical_reference_vertices = rig_output_vertices[0].detach().cpu().numpy()
        # Anny's forward pass retains its leading batch dimension (1, N, 3);
        # strip that singleton dimension before converting individual points.
        rig_vertices = tuple(
            (float(vertex[0]) * 1000.0, float(vertex[1]) * 1000.0, float(vertex[2]) * 1000.0)
            for vertex in rig_output_vertices[0]
        )

    if fit_hip:
        # Only the hip-specific morphs may move while fitting hip circumference.
        # All other local and global shape controls are now frozen.
        for name, value in body.local_changes_kwargs.items():
            value.requires_grad_(name in hip_change_names)
        hip_parameters = [
            value for name, value in body.local_changes_kwargs.items() if name in hip_change_names
        ]
        _hip_name, hip_key, hip_target = hip_targets[0]
        hip_target_value = torch.tensor(hip_target, dtype=torch.float32)
        hip_optimizer = torch.optim.Adam(hip_parameters, lr=0.035)
        for _step in range(fit_steps):
            hip_optimizer.zero_grad(set_to_none=True)
            actual = measure_grad(body, only=[hip_key])
            relative_error = (
                actual[hip_key] - hip_target_value
            ).abs() / hip_target_value.clamp_min(1.0)
            if float(relative_error.max().detach()) <= _FIT_TOLERANCE:
                break
            measurement_loss = (
                ((actual[hip_key] - hip_target_value) / hip_target_value.clamp_min(1.0))
                .square()
                .mean()
            )
            hip_penalty = torch.stack(
                [
                    value.square().mean()
                    for name, value in body.local_changes_kwargs.items()
                    if name in hip_change_names
                ]
            ).mean()
            loss = measurement_loss + 0.0005 * hip_penalty
            loss.backward()
            hip_optimizer.step()
            with torch.no_grad():
                for name, value in body.local_changes_kwargs.items():
                    if name in hip_change_names:
                        value.clamp_(-1.0, 1.0)

    for value in body.local_changes_kwargs.values():
        value.requires_grad_(False)

    with torch.no_grad():
        output = model(
            pose_parameters=pose,
            phenotype_kwargs=body.phenotype_kwargs,
            local_changes_kwargs=body.local_changes_kwargs,
            pose_parameterization="local-bone",
            return_bone_ends=True,
        )
    if os.environ.get("CLOTH_ANNY_SHAPE_TRACE") == "1":
        fitted_front_y = _front_y_mm(output["vertices"])
        breast_names = {
            name: float(value.detach().reshape(-1)[0].item())
            for name, value in body.local_changes_kwargs.items()
            if "bust" in name or "underbust" in name or "breast" in name
        }
        _write_shape_trace(
            "post-local-fit",
            {
                "gender": float(body.phenotype_kwargs["gender"].detach().item()),
                "cupsize": float(body.phenotype_kwargs["cupsize"].detach().item()),
                "front_lobe_y_mm": fitted_front_y,
                "bust_morphs": breast_names,
            },
        )
        print(
            "anny-shape-trace stage=post-fit gender=%s cupsize=%s front_lobe_y_mm=%r bust_morphs=%r"
            % (
                float(body.phenotype_kwargs["gender"].detach().item()),
                float(body.phenotype_kwargs["cupsize"].detach().item()),
                fitted_front_y,
                breast_names,
            ),
            flush=True,
        )

    fitted_body = load_anny_from_verts(
        output["vertices"],
        model,
        phenotype_kwargs=body.phenotype_kwargs,
        local_changes_kwargs=body.local_changes_kwargs,
        bone_heads=output.get("bone_heads"),
        bone_tails=output.get("bone_tails"),
        source="FreeCAD Cloth / Anny",
    )
    if canonical_reference_vertices is not None:
        # Keep the post-hip surface in the pre-hip coordinate frame. Also update
        # clad-body's XY offset so its measured bone/joint positions stay aligned.
        reference_vertices, _ = _canonicalize_anny_vertices(
            canonical_reference_vertices,
            canonical_reference_vertices,
        )
        fitted_vertices, center_xy = _canonicalize_anny_vertices(
            output["vertices"][0].detach().cpu().numpy(),
            canonical_reference_vertices,
        )
        fitted_body.vertices = _localize_hip_fit_delta(reference_vertices, fitted_vertices)
        fitted_body._xy_offset = (-center_xy).astype(np.float32)

    all_vertices = fitted_body.vertices
    fitted_faces = fitted_body.faces
    if len(fitted_faces.shape) != 2 or fitted_faces.shape[1] != 3:
        raise AnnyAvatarBackendError(
            "Anny's MakeHuman topology must be triangulated; expected a face array of shape (N, 3)."
        )
    if len(all_vertices) < MAKEHUMAN_BODY_VERTEX_COUNT:
        raise AnnyAvatarBackendError(
            "The installed Anny topology is incompatible with the MakeHuman rig: "
            f"expected at least {MAKEHUMAN_BODY_VERTEX_COUNT} indexed vertices, "
            f"received {len(all_vertices)}."
        )

    # Keep display vertices and rig vertices in the same complete source-index
    # space. The visible surface uses the hip-fitted result, while rig anchors
    # use the pre-hip snapshot returned by the same fitting pass.
    surface_vertices: tuple[tuple[float, float, float], ...] = tuple(
        (float(vertex[0]) * 1000.0, float(vertex[1]) * 1000.0, float(vertex[2]) * 1000.0)
        for vertex in all_vertices
    )
    # Keep helper/rig vertices untouched and apply the visible breast correction
    # only within HM08's canonical body prefix, preserving vertex-index topology.
    visible_vertices = _apply_front_breast_fullness(
        surface_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT],
        float(breast_size),
        float(dict(measurements).get("height", 1750.0)),
    )
    surface_vertices = visible_vertices + surface_vertices[MAKEHUMAN_BODY_VERTEX_COUNT:]
    if len(base_ids) != len(surface_vertices) or base_ids != list(range(len(base_ids))):
        raise AnnyAvatarBackendError(
            "Anny's full vertex index map does not preserve the original HM08 rig index space."
        )
    if rig_vertices is None:
        rig_vertices = surface_vertices
    elif len(rig_vertices) != len(surface_vertices):
        raise AnnyAvatarBackendError(
            "Anny's hip-neutral rig snapshot does not preserve the surface vertex index space."
        )
    vertices = surface_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT]
    triangles: tuple[tuple[int, int, int], ...] = tuple(
        (int(face[0]), int(face[1]), int(face[2]))
        for face in fitted_body.faces
        if len(face) == 3 and all(0 <= int(index) < MAKEHUMAN_BODY_VERTEX_COUNT for index in face)
    )
    if len(triangles) < 20_000:
        raise AnnyAvatarBackendError(
            "Anny produced too few triangles for the visible HM08 body surface: "
            f"expected at least 20000, received {len(triangles)}."
        )
    # Anny's triangulation preserves the right vertex index space but may contain
    # locally reversed faces. Repair winding without changing either index set,
    # so vertex normals, skin padding, and the closed-mesh collision projector agree.
    from freecad_cloth.avatar.MeshSanity import orient_closed_triangle_winding

    try:
        triangles = orient_closed_triangle_winding(vertices, triangles)
    except ValueError as exc:
        raise AnnyAvatarBackendError(
            f"Anny's visible HM08 surface is not a closed orientable mesh: {exc}"
        ) from exc
    result = MeshData(vertices, triangles)
    try:
        result.validate()
    except (TypeError, ValueError, RuntimeError) as exc:
        raise AnnyAvatarBackendError(f"Anny produced an invalid body mesh: {exc}") from exc
    return result, rig_vertices


@lru_cache(maxsize=16)
def _cached_fitted_body(
    measurements: tuple[tuple[str, float], ...],
    gender: float,
    breast_size: float,
    phenotype_overrides: tuple[tuple[str, float], ...],
    local_change_overrides: tuple[tuple[str, float], ...],
    mass_target_kg: float | None,
    fit_hip: bool,
    fit_steps: int,
) -> tuple[MeshData, tuple[tuple[float, float, float], ...]]:
    """Cache fitted surface and full rig vertices so viewport events do not refit."""
    return _fit_anny_body(
        measurements,
        gender,
        breast_size,
        phenotype_overrides,
        local_change_overrides,
        mass_target_kg,
        fit_hip=fit_hip,
        fit_steps=fit_steps,
    )


def _fitted_body_for(
    parameters: AvatarParameters,
    *,
    fit_hip: bool = True,
) -> tuple[MeshData, tuple[tuple[float, float, float], ...]]:
    """Return the cached shape and rig-indexed vertices for the selected fit contract."""
    fit_measurement_keys = {name for name, _key in MEASUREMENT_FIELDS}
    measurement_values = {
        str(name): float(value)
        for name, value in parameters.measurements.items()
        if str(name) in fit_measurement_keys
    }
    if not fit_hip:
        # Hip circumference controls visible hip surface only, not the skeleton.
        from freecad_cloth.avatar.AvatarModel import DEFAULT_MEASUREMENTS

        measurement_values["hip"] = float(DEFAULT_MEASUREMENTS["hip"])
    key = tuple(sorted(measurement_values.items()))
    return _cached_fitted_body(
        key,
        float(parameters.gender),
        float(parameters.breast_size),
        tuple(sorted(parameters.phenotype_overrides.items())),
        tuple(sorted(parameters.local_change_overrides.items())),
        parameters.mass_target_kg,
        fit_hip,
        _configured_fit_steps(),
    )


def build_avatar_rig_vertices(
    parameters: AvatarParameters,
) -> tuple[tuple[float, float, float], ...]:
    """Return cached hip-neutral Anny vertices for stable skeleton anchor mapping."""
    _mesh, rig_vertices = _fitted_body_for(parameters, fit_hip=False)
    return rig_vertices


def build_avatar_shape_mesh(
    parameters: AvatarParameters,
    *,
    include_skin_offset: bool = True,
) -> MeshData:
    """Return a cached Anny mannequin in millimetres and its native triangulation."""
    mesh, _rig_vertices = _fitted_body_for(parameters)
    if not include_skin_offset or parameters.skin_offset <= 0:
        return mesh

    # Preserve Cloth's optional collision/surface padding using trimesh's native
    # vertex normals; the body shape itself still comes from Anny.
    import numpy as np
    import trimesh

    surface = trimesh.Trimesh(
        vertices=np.asarray(mesh.vertices, dtype=float),
        faces=np.asarray(mesh.triangles, dtype=np.int64),
        process=False,
    )
    normals = np.asarray(surface.vertex_normals, dtype=float)
    offset = float(parameters.skin_offset)
    padded: tuple[tuple[float, float, float], ...] = tuple(
        (
            float(point[0] + offset * normal[0]),
            float(point[1] + offset * normal[1]),
            float(point[2] + offset * normal[2]),
        )
        for point, normal in zip(mesh.vertices, normals, strict=True)
    )
    return MeshData(padded, mesh.triangles).validate()
