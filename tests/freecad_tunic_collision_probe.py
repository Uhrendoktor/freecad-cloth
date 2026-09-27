"""Research-only collision/stitch telemetry for the canonical tunic."""
from __future__ import annotations

import json
import math
import os
import traceback
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "freecad_screenshot_source.py"
OUT = Path(os.environ.get("TUNIC_COLLISION_PROBE_OUT", str(ROOT / "artifacts" / "tunic-collision-probe.json")))


class ProbeComplete(RuntimeError):
    pass


def _load_source_namespace():
    text = SOURCE.read_text(encoding="utf-8")
    prefix = text.split("exit_code = 0", 1)[0]
    ns = {"__name__": "__tunic_collision_probe__", "__file__": str(SOURCE)}
    exec(compile(prefix, str(SOURCE), "exec"), ns, ns)
    return ns


def _surface_mesh(surface):
    import numpy as np
    import trimesh
    mesh = trimesh.Trimesh(
        vertices=np.asarray(surface.vertices, dtype=float),
        faces=np.asarray(surface.triangles, dtype=int),
        process=False,
    )
    mesh.fix_normals()
    return mesh


def _stitch_metrics(proxy, positions):
    import numpy as np
    points = np.asarray(positions, dtype=float)
    lengths = []
    for pairs in getattr(proxy, "seam_stitch_pairs", {}).values():
        for a, b in pairs:
            lengths.append(float(np.linalg.norm(points[int(a)] - points[int(b)])))
    if not lengths:
        return {"count": 0, "max_mm": None, "mean_mm": None}
    return {"count": len(lengths), "max_mm": max(lengths), "mean_mm": sum(lengths) / len(lengths)}


def _record(scene, step, previous, mesh, source_surface):
    import numpy as np
    positions = tuple(scene.Proxy.backend.positions())
    points = np.asarray(positions, dtype=float)
    closest, distances, triangle_ids = mesh.nearest.on_surface(points)
    distances = np.asarray(distances, dtype=float)
    triangle_ids = np.asarray(triangle_ids, dtype=int)
    contact = distances <= 2.0
    inside = None
    if bool(getattr(mesh, "is_watertight", False)):
        try:
            inside = [bool(v) for v in mesh.contains(points)]
        except Exception:
            inside = None

    inside_count = outside_count = None
    signed = distances.copy()
    if inside is not None:
        mask = np.asarray(inside, dtype=bool)
        inside_count = int(np.count_nonzero(mask))
        on_surface = distances <= 1e-6
        outside_count = int(len(points) - inside_count - np.count_nonzero(on_surface))
        signed[mask] *= -1.0

    outward = inward = tangential = 0
    observations = []
    if previous is not None and len(previous) == len(points):
        delta = points - np.asarray(previous, dtype=float)
        normals = np.asarray(mesh.face_normals[np.maximum(triangle_ids, 0)], dtype=float)
        dots = np.sum(delta * normals, axis=1)
        for idx in np.flatnonzero(contact & np.isfinite(dots)):
            value = float(dots[int(idx)])
            if value > 1e-6:
                outward += 1
                orientation = "outward"
            elif value < -1e-6:
                inward += 1
                orientation = "inward"
            else:
                tangential += 1
                orientation = "tangential"
            observations.append({
                "particle_index": int(idx),
                "distance_mm": float(distances[int(idx)]),
                "surface_triangle": int(triangle_ids[int(idx)]),
                "normal_dot_displacement_mm": value,
                "orientation": orientation,
            })

    solver_surface = getattr(scene.Proxy.backend, "solver_collision_surface", None)
    return {
        "step": int(step),
        "particle_count": len(points),
        "min_surface_distance_mm": float(np.min(distances)),
        "mean_surface_distance_mm": float(np.mean(distances)),
        "contact_band_count_le_2mm": int(np.count_nonzero(contact)),
        "contact_band_fraction": float(np.mean(contact)),
        "inside_count": inside_count,
        "outside_count": outside_count,
        "on_surface_count": int(np.count_nonzero(distances <= 1e-6)),
        "signed_distance_min_mm": float(np.min(signed)),
        "signed_distance_max_mm": float(np.max(signed)),
        "response_orientation": {
            "outward": outward,
            "inward": inward,
            "tangential": tangential,
            "observations": observations,
        },
        "source_triangle_count": len(source_surface.triangles),
        "solver_triangle_count": 0 if solver_surface is None else len(solver_surface.triangles),
        "stitch_lengths_mm": _stitch_metrics(scene.Proxy, positions),
    }, positions


def _write(payload):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    states = payload["states"]
    if len(states) != 31 or states[0]["step"] != 0 or states[-1]["step"] != 30:
        raise RuntimeError("probe must contain exact states 0..30")
    print(
        "tunic-collision-probe=passed states=%d first_contact_step=%s source_triangles=%d solver_triangles=%d initial_stitch_max_mm=%.3f"
        % (
            len(states),
            payload["first_contact_step"],
            payload["source_triangle_count"],
            payload["solver_triangle_count"],
            float(states[0]["stitch_lengths_mm"]["max_mm"] or 0.0),
        ),
        flush=True,
    )


def main():
    if Gui.getMainWindow() is None:
        raise RuntimeError("FreeCAD GUI did not launch")
    Gui.getMainWindow().show()
    canonical = _load_source_namespace()
    init_gui = ROOT / "InitGui.py"
    exec(compile(init_gui.read_text(encoding="utf-8"), str(init_gui), "exec"), canonical, canonical)
    original_panel = canonical["SimulationQualityTaskPanel"]

    class ProbePanel(original_panel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            scene = self.scene
            backend = getattr(scene.Proxy, "backend", None)
            source_surface = getattr(scene.Proxy, "collision_surface", None)
            if backend is None or source_surface is None:
                raise RuntimeError("probe scene missing backend/collision surface")
            self._probe_mesh = _surface_mesh(source_surface)
            self._probe_surface = source_surface
            self._probe_states = []
            record, previous = _record(scene, 0, None, self._probe_mesh, source_surface)
            self._probe_states.append(record)
            self._probe_previous = previous

        def step(self, count):
            remaining = int(count)
            while remaining:
                super().step(1)
                step = int(self.scene.Steps)
                record, previous = _record(
                    self.scene, step, self._probe_previous, self._probe_mesh, self._probe_surface
                )
                self._probe_states.append(record)
                self._probe_previous = previous
                remaining -= 1
                if step >= 30:
                    state = self._probe_states
                    contacts = [row["contact_band_count_le_2mm"] for row in state]
                    payload = {
                        "schema": 1,
                        "probe_kind": "research-only-tunic-collision-and-stitch",
                        "derived_telemetry": True,
                        "source_head": os.environ.get("GITHUB_SHA", "unknown"),
                        "source_file": str(SOURCE.relative_to(ROOT)),
                        "source_mesh_watertight": bool(self._probe_mesh.is_watertight),
                        "source_mesh_winding_consistent": bool(self._probe_mesh.is_winding_consistent),
                        "source_triangle_count": len(self._probe_surface.triangles),
                        "solver_triangle_count": int(state[-1]["solver_triangle_count"]),
                        "first_contact_step": next((i for i, n in enumerate(contacts) if n > 0), None),
                        "production_config": {
                            "particle_distance_mm": float(getattr(self.scene, "ParticleDistance", 0.0)),
                            "solver_iterations": int(getattr(self.scene, "SolverIterations", 0)),
                            "solver_substeps": int(getattr(self.scene, "SolverSubsteps", 0)),
                            "time_step": float(getattr(self.scene, "TimeStep", 0.0)),
                            "gravity_z": float(getattr(self.scene, "GravityZ", 0.0)),
                            "fabric_friction": float(getattr(self.scene, "FabricFriction", 0.0)),
                            "pin_mode": str(getattr(self.scene, "PinMode", "")),
                            "pin_selection": list(getattr(self.scene, "PinSelection", ()) or ()),
                            "collision_mode": os.environ.get("CLOTH_TISSU_COLLISION_MODE", ""),
                            "collision_triangle_limit": int(os.environ.get("CLOTH_TISSU_COLLISION_TRIANGLES", "0")),
                        },
                        "notes": [
                            "All particle distances and stitch lengths are derived telemetry.",
                            "Displacement-vs-face-normal orientation is a derived motion diagnostic, not native contact telemetry.",
                            "Tissu stitches remain rest-length 0.0; this probe does not change compliance or solver settings.",
                        ],
                        "states": state,
                    }
                    _write(payload)
                    raise ProbeComplete()

    canonical["SimulationQualityTaskPanel"] = ProbePanel
    canonical["save"] = lambda *args, **kwargs: None
    try:
        canonical["simulation"]()
    except ProbeComplete:
        return
    finally:
        for document in list(App.listDocuments().values()):
            try:
                App.closeDocument(document.Name)
            except Exception:
                pass


if __name__ == "__main__":
    try:
        main()
    except ProbeComplete:
        raise SystemExit(0)
    except BaseException as exc:
        print("TUNIC COLLISION PROBE FAILURE: %r" % (exc,), flush=True)
        print(traceback.format_exc(), flush=True)
        raise SystemExit(1)
