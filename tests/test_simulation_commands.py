"""FreeCAD-independent contract checks for Simulation workbench commands."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "SimulationCommands.py").read_text()

assert '"ClothSimulation_Step"' in source
assert '"ClothSimulation_Run"' in source
assert '"ClothSimulation_Reset"' in source
assert 'def run_simulation(steps=30):' in source
assert 'def reset_simulation():' in source
assert 'def simulation_status():' in source
assert 'def IsActive(self):' in source
assert '_has_simulation' in source
assert '"state": "unavailable"' in source
assert '"state": "ready" if finite else "invalid/non-finite"' in source

# Lifecycle actions must not create a hidden scene: only the explicit Create
# commands are allowed to create one when no simulation exists.
run_body = source.split("def run_simulation", 1)[1].split("def reset_simulation", 1)[0]
reset_body = source.split("def reset_simulation", 1)[1].split("def simulation_status", 1)[0]
assert "create_simulation()" not in run_body
assert "create_simulation()" not in reset_body

print("Simulation lifecycle command contract passed")
