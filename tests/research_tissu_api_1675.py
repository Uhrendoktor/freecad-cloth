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
    print("TISSU_API_PROBE " + json.dumps(info, sort_keys=True, default=str))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
