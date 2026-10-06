"""Production tunic visual audit.

Keep the production acceptance path on the repository's validated tunic profile
instead of maintaining a second, divergent fixture implementation.  The delegated
profile exercises the native Sketcher garment, PositionBasedDynamics realtime preview, finite
simulation, visual sanity checks, and the six-side screenshot audit.
"""

import os
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
validated = ROOT / "tests" / "freecad_tunic_audit.py"
source = validated.read_text(encoding="utf-8")
try:
    exec(compile(source, str(validated), "exec"), globals(), globals())
except BaseException as exc:
    print("production-tunic-audit-wrapper-failed", repr(exc), flush=True)
    print(traceback.format_exc(), flush=True)
    os._exit(1)
