"""Production tunic visual audit.

Keep the production acceptance path on the repository's validated tunic profile
instead of maintaining a second, divergent fixture implementation.  The delegated
profile exercises the native Sketcher garment, Tissu realtime preview, finite
simulation, visual sanity checks, and the six-side screenshot audit.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
validated = ROOT / "tests" / "freecad_tunic_audit.py"
source = validated.read_text(encoding="utf-8")
exec(compile(source, str(validated), "exec"), globals(), globals())
