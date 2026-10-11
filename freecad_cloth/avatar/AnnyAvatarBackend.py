"""Anny-backed avatar generation and measurement fitting.

This module deliberately delegates human shape generation and anthropometric
measurement to Anny and clad-body. It does not deform vertices directly:
measurements are fitted through the libraries' differentiable body model.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from freecad_cloth.avatar.HumanoidMesh import MAKEHUMAN_BODY_VERTEX_COUNT, MeshData

if TYPE_CHECKING:
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
    "measure-shoulder-dist",
    "torso-scale-horiz",
)
_BREAST_LOCAL_CHANGE = "breast-volume-vert-up"
_FIT_STEPS = max(1, int(os.environ.get("FREECAD_CLOTH_ANNY_FIT_STEPS", "40")))
_FIT_TOLERANCE = 0.012


class AnnyAvatarBackendError(RuntimeError):
    """Raised when Anny cannot produce a compatible avatar mesh."""


class _ForwardModel(Protocol):
    """Minimal writable model interface needed for the compatibility adapter."""

    forward: Callable[..., object]


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
def _measurement_local_change_labels() -> tuple[str, ...]:
    """Return only relevant local modifiers present in the installed Anny assets."""
    try:
        import anny
    except ImportError as exc:
        raise AnnyAvatarBackendError(
            "Anny is required for parametric mannequin generation; install "
            "'anny>=0.6,<0.7' and 'clad-body[anny]>=0.6.1,<0.7' in the FreeCAD Python environment."
        ) from exc

    # Anny 0.6 provides get_anny_root_dir(); keep a package-relative fallback
    # for installations that omit the helper.
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
    wanted = (*_LOCAL_CHANGE_TERMS, _BREAST_LOCAL_CHANGE)
    for group, group_data in metadata.items():
        if group == "genitals" or not isinstance(group_data, dict):
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
                    and any(term in positive for term in wanted)
                ):
                    selected.add(positive)

    if _BREAST_LOCAL_CHANGE not in selected:
        raise AnnyAvatarBackendError(
            f"Anny assets do not provide the {_BREAST_LOCAL_CHANGE!r} shape control."
        )
    return tuple(sorted(selected))


def _initial_phenotypes(gender: float, breast_size: float) -> dict[str, float | dict[str, float]]:
    """Translate Cloth's UI controls into Anny's published phenotype convention."""
    return {
        # Anny's gender endpoints are male=0 and female=1; Cloth uses the
        # inverse convention for its user-facing slider.
        "gender": 1.0 - gender,
        "age": 0.667,  # young-adult body shape
        "muscle": 0.5,
        "weight": 0.5,
        "height": 0.5,
        "proportions": 0.5,
        "cupsize": 0.5,
        "firmness": 0.5,
        # Keep the unexposed race controls at Anny's neutral equal blend.
        "african": 1.0 / 3.0,
        "asian": 1.0 / 3.0,
        "caucasian": 1.0 / 3.0,
        "_local_changes": {
            name: breast_size if name == _BREAST_LOCAL_CHANGE else 0.0
            for name in _measurement_local_change_labels()
        },
    }


def _fit_anny_body(
    measurements: tuple[tuple[str, float], ...],
    gender: float,
    breast_size: float,
) -> tuple[MeshData, tuple[tuple[float, float, float], ...]]:
    """Fit an Anny body and preserve every indexed vertex for rig anchors."""
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
    initial_parameters = _initial_phenotypes(gender, breast_size)
    local_values = initial_parameters.pop("_local_changes")
    if not isinstance(local_values, dict):
        raise AnnyAvatarBackendError("Anny local-change parameters were not resolved.")
    phenotype_values = {
        name: float(value)
        for name, value in initial_parameters.items()
        if isinstance(value, (int, float))
    }

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

    phenotype_kwargs = {
        name: torch.tensor(
            [phenotype_values[name]], dtype=torch.float32, device="cpu", requires_grad=True
        )
        for name in model.phenotype_labels
        if name in phenotype_values
    }
    missing_phenotypes = set(model.phenotype_labels) - set(phenotype_kwargs)
    if missing_phenotypes:
        raise AnnyAvatarBackendError(
            "Anny requires phenotype controls that Cloth has not initialized: "
            + ", ".join(sorted(missing_phenotypes))
        )

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
    optimized_phenotypes = {"height", "weight", "muscle", "proportions"}
    if body.phenotype_kwargs is None or body.local_changes_kwargs is None:
        raise AnnyAvatarBackendError("Anny did not expose trainable phenotype/local-change inputs.")

    optimizer_parameters: list[torch.Tensor] = []
    initial_values: dict[tuple[str, str], torch.Tensor] = {}
    for name, value in body.phenotype_kwargs.items():
        trainable = name in optimized_phenotypes
        value.requires_grad_(trainable)
        if trainable:
            optimizer_parameters.append(value)
            initial_values[("phenotype", name)] = value.detach().clone()

    breast_names = {_BREAST_LOCAL_CHANGE}
    for name, value in (body.local_changes_kwargs or {}).items():
        trainable = name not in breast_names
        value.requires_grad_(trainable)
        if trainable:
            optimizer_parameters.append(value)
            initial_values[("local", name)] = value.detach().clone()

    if not optimizer_parameters:
        raise AnnyAvatarBackendError("Anny exposes no trainable shape parameters.")

    optimizer = torch.optim.Adam(optimizer_parameters, lr=0.035)
    target_keys = [key for _name, key, _target in targets]
    target_values = {
        key: torch.tensor(target, dtype=torch.float32) for _name, key, target in targets
    }

    for _step in range(_FIT_STEPS):
        optimizer.zero_grad(set_to_none=True)
        actual = measure_grad(body, only=target_keys)
        relative_errors = [
            (actual[key] - target_values[key]).abs() / target_values[key].clamp_min(1.0)
            for _name, key, _target in targets
        ]
        max_error = float(torch.stack(relative_errors).max().detach())
        if max_error <= _FIT_TOLERANCE:
            break

        measurement_loss = torch.stack(
            [
                ((actual[key] - target_values[key]) / target_values[key].clamp_min(1.0)) ** 2
                for _name, key, _target in targets
            ]
        ).mean()

        # Prefer the requested measurements while discouraging unnecessarily
        # extreme global phenotypes and local target weights.
        phenotype_penalty = torch.zeros((), dtype=torch.float32)
        local_penalty = torch.zeros((), dtype=torch.float32)
        for (kind, _name), initial in initial_values.items():
            current = (
                body.phenotype_kwargs[_name]
                if kind == "phenotype"
                else body.local_changes_kwargs[_name]
            )
            penalty = (current - initial).square().mean()
            if kind == "phenotype":
                phenotype_penalty = phenotype_penalty + penalty
            else:
                local_penalty = local_penalty + current.square().mean()
        loss = measurement_loss + 0.002 * phenotype_penalty + 0.0005 * local_penalty
        loss.backward()
        optimizer.step()

        with torch.no_grad():
            for name in optimized_phenotypes:
                if name in body.phenotype_kwargs:
                    body.phenotype_kwargs[name].clamp_(0.0, 1.0)
            for name, value in (body.local_changes_kwargs or {}).items():
                if name not in breast_names:
                    value.clamp_(-1.0, 1.0)

    model = body.model
    if body.phenotype_kwargs is None:
        raise AnnyAvatarBackendError("Anny did not preserve the fitted phenotype tensors.")
    if body.local_changes_kwargs is None:
        raise AnnyAvatarBackendError("Anny did not preserve the fitted morph tensors.")
    first_parameter = next(iter(body.phenotype_kwargs.values()))
    pose = build_anny_apose(model, first_parameter.device)
    with torch.no_grad():
        output = model(
            pose_parameters=pose,
            phenotype_kwargs=body.phenotype_kwargs,
            local_changes_kwargs=body.local_changes_kwargs,
            pose_parameterization="local-bone",
            return_bone_ends=True,
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

    # The fitted Anny array retains the complete source-index space, including
    # unreferenced HM08 helper vertices used by the authored MakeHuman skeleton.
    # These vertices are necessary for rig joint anchors but must not be shown
    # as anatomy: the public surface remains the first 13,380 body vertices.
    rig_vertices: tuple[tuple[float, float, float], ...] = tuple(
        (
            float(vertex[0]) * 1000.0,
            float(vertex[1]) * 1000.0,
            float(vertex[2]) * 1000.0,
        )
        for vertex in all_vertices
    )
    if len(base_ids) != len(rig_vertices) or base_ids != list(range(len(base_ids))):
        raise AnnyAvatarBackendError(
            "Anny's full vertex index map does not preserve the original HM08 rig index space."
        )
    vertices = rig_vertices[:MAKEHUMAN_BODY_VERTEX_COUNT]
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
) -> tuple[MeshData, tuple[tuple[float, float, float], ...]]:
    """Cache fitted surface and full rig vertices so viewport events do not refit."""
    return _fit_anny_body(measurements, gender, breast_size)


def _fitted_body_for(
    parameters: AvatarParameters,
) -> tuple[MeshData, tuple[tuple[float, float, float], ...]]:
    """Return the cached visible surface and complete rig-indexed fitted vertices."""
    key = tuple(
        sorted((str(name), float(value)) for name, value in parameters.measurements.items())
    )
    return _cached_fitted_body(key, float(parameters.gender), float(parameters.breast_size))


def build_avatar_rig_vertices(
    parameters: AvatarParameters,
) -> tuple[tuple[float, float, float], ...]:
    """Return all fitted Anny vertices in millimetres for legacy rig joint indices."""
    _mesh, rig_vertices = _fitted_body_for(parameters)
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
