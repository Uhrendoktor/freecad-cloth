"""Persisted user-facing lifecycle for the native cloth simulation object.

The status is deliberately small and FreeCAD-independent so document objects,
headless tests, and the task panel share the same state vocabulary.
"""

STATUS_NAMES = ("Ready", "Running", "Complete", "Invalid")

# Changes to any of these inputs invalidate the previously computed result.
INPUT_PROPERTIES = frozenset({
    "QualityPreset",
    "ParticleDistance",
    "SolverIterations",
    "SolverSubsteps",
    "FabricDensity",
    "FabricThickness",
    "FabricStretch",
    "FabricShear",
    "FabricBend",
    "FabricFriction",
    "AvatarSkinOffset",
    "CollisionRadius",
    "Steps",
})


def status_after_execute(*, steps, finite):
    """Return the terminal status after a successful recompute."""
    if not finite:
        return "Invalid"
    return "Complete" if int(steps) > 0 else "Ready"


def invalidation_message(property_name):
    """Return a stable diagnostic for a result invalidated by an input change."""
    return f"Simulation invalidated by {property_name}; recompute to update the result."


def status_message(status, *, steps=0, simulated_time=0.0, particles=0, detail=""):
    """Build a concise task-panel message from persisted simulation state."""
    text = f"{status} | {float(simulated_time):.3f} s | {int(particles)} particles | {int(steps)} steps"
    return f"{text} | {detail}" if detail else text
