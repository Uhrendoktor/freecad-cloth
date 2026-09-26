"""Research-only probe for issue #1675: inspect public pytissu state-mutation APIs."""
import importlib.metadata
import json
import sys
import traceback

def public_names(obj):
    return sorted(n for n in dir(obj) if not n.startswith("_"))

def safe_type(obj):
    try:
        return type(obj).__module__ + "." + type(obj).__name__
    except Exception:
        return type(obj).__name__

def main():
    import tissu

    info = {
        "python": sys.version,
        "pytissu_version": importlib.metadata.version("pytissu"),
        "tissu_file": getattr(tissu, "__file__", ""),
        "simulation_public": public_names(tissu.Simulation),
    }

    sim = tissu.Simulation(substeps=1, iterations=1, thickness=0.002)
    cloth = sim.create_grid(name="probe", rows=3, cols=3, spacing=0.01, material="cotton")
    sim_public = public_names(sim)
    cloth_public = public_names(cloth)
    instance = getattr(cloth, "instance", None)
    instance_public = public_names(instance) if instance is not None else []
    solver = getattr(sim, "solver", None)
    solver_public = public_names(solver) if solver is not None else []

    info.update({
        "simulation_type": safe_type(sim),
        "simulation_instance_public": sim_public,
        "cloth_type": safe_type(cloth),
        "cloth_public": cloth_public,
        "cloth_instance_type": safe_type(instance),
        "cloth_instance_public": instance_public,
        "solver_type": safe_type(solver),
        "solver_public": solver_public,
        "positions_attr_type": safe_type(getattr(sim, "positions", None)) if hasattr(sim, "positions") else None,
        "positions_is_sequence": hasattr(getattr(sim, "positions", None), "__len__"),
        "positions_value_len": len(sim.positions) if hasattr(sim, "positions") and hasattr(sim.positions, "__len__") else None,
    })

    mutable_candidates = []
    for obj_name, obj in (("simulation", sim), ("cloth", cloth), ("instance", instance), ("solver", solver)):
        if obj is None:
            continue
        for name in public_names(obj):
            if any(k in name.lower() for k in ("position", "velocity", "state", "particle", "reset", "set_")):
                try:
                    value = getattr(obj, name)
                    mutable_candidates.append({
                        "object": obj_name,
                        "name": name,
                        "type": safe_type(value),
                        "callable": callable(value),
                    })
                except Exception as exc:
                    mutable_candidates.append({
                        "object": obj_name,
                        "name": name,
                        "error": type(exc).__name__ + ":" + str(exc),
                    })

    info["mutation_candidates"] = mutable_candidates
    import numpy as np
    sim_positions = np.asarray(sim.positions)
    cloth_positions = np.asarray(cloth.positions)
    solver_particles = solver.get_particles()
    info["shares_sim_cloth_positions"] = bool(np.shares_memory(sim_positions, cloth_positions))
    info["solver_particles_type"] = safe_type(solver_particles)
    info["solver_particles_public"] = public_names(solver_particles)
    before = np.array(sim_positions, copy=True)
    sim.positions[0] = sim.positions[0] + np.asarray([0.001, 0.0, 0.0], dtype=float)
    info["direct_position_write_visible"] = bool(np.linalg.norm(np.asarray(sim.positions[0]) - before[0]) > 0.0005)
    info["direct_position_delta_m"] = float(np.linalg.norm(np.asarray(sim.positions[0]) - before[0]))
    sim.step(1.0 / 60.0)
    after_step = np.asarray(sim.positions)
    info["post_step_finite"] = bool(np.isfinite(after_step).all())
    info["post_step_max_displacement_m"] = float(np.max(np.linalg.norm(after_step - before, axis=1)))
    info["post_step_kinetic_energy"] = float(sim.kinetic_energy())

    print("TISSU_API_PROBE " + json.dumps(info, sort_keys=True, default=str))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
