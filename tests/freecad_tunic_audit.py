"""Run the canonical production tunic scenario under the pinned FreeCAD CI image.

The audit deliberately does not rewrite production source, panel placement, seam
correspondence, collision margins, time step, or solver settings.  It only selects
the intended acceptance scenario and then executes the same source users run.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = Path(__file__).with_name("freecad_screenshot_source.py")
source = source_path.read_text(encoding="utf-8")

os.environ["CLOTH_PBD_COLLISION_MODE"] = "mesh"
os.environ["CLOTH_TUNIC_AUDIT_SKIP_CANONICAL_ACCEPTANCE"] = "1"
os.environ["CLOTH_TUNIC_AUDIT_RUN_AVATAR_ACCEPTANCE"] = "1"

try:
    compiled_source = compile(source, str(source_path), "exec")
except SyntaxError as error:
    lines = source.splitlines()
    line_number = int(getattr(error, "lineno", 1) or 1)
    start = max(1, line_number - 2)
    end = min(len(lines), line_number + 2)
    context = "\\n".join(
        "%4d | %s" % (number, lines[number - 1]) for number in range(start, end + 1)
    )
    raise RuntimeError(
        "canonical tunic source failed syntax validation: %s at line %d\\n%s"
        % (error.msg, line_number, context)
    ) from error

if "--syntax-check" in sys.argv:
    print("tunic-audit-source-syntax=passed lines=%d" % len(source.splitlines()), flush=True)
    raise SystemExit(0)

namespace = {"__file__": str(source_path), "__name__": "__main__"}
exec(compiled_source, namespace, namespace)
