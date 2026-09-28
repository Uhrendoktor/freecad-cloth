#!/usr/bin/env bash
set -euo pipefail

: "${FREECAD_TUNIC_IMAGE:?FREECAD_TUNIC_IMAGE must be set}"
: "${CLOTH_HEAD_SHA:?CLOTH_HEAD_SHA must be set}"

root="artifacts/tissu-substep-probe"
rm -rf "$root"
mkdir -p "$root"

for substeps in 1 2 4 8 10; do
  candidate="$root/$substeps"
  mkdir -p "$candidate"
  docker run --rm --init --security-opt seccomp=unconfined --shm-size=1g \
    -e TINI_SUBREAPER=1 -e DISPLAY=:99 -e XDG_RUNTIME_DIR=/tmp/runtime-cloth \
    -e PYTHONPATH=/workspace -e QT_X11_NO_MITSHM=1 -e QT_QPA_PLATFORM=xcb \
    -e LIBGL_ALWAYS_SOFTWARE=1 -e CLOTH_SIMULATION_BACKEND=tissu \
    -e CLOTH_TISSU_SUBSTEPS="$substeps" -e CLOTH_TISSU_COLLISION_MODE=mesh \
    -e CLOTH_TISSU_COLLISION_TRIANGLES=2048 \
    -v "$PWD:/workspace" -w /workspace "$FREECAD_TUNIC_IMAGE" bash -lc "
      set -euo pipefail
      python3 -m pip install --no-cache-dir triangle==20250106 >/tmp/triangle-install.log 2>&1
      rm -rf /workspace/docs/images/generated
      mkdir -p /workspace/docs/images/generated /tmp/runtime-cloth
      Xvfb :99 -screen 0 1280x720x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & XVFB=\$!
      openbox >/tmp/openbox.log 2>&1 & OPENBOX=\$!
      trap 'kill \$OPENBOX \$XVFB 2>/dev/null || true' EXIT
      for i in \$(seq 1 12); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep 0.25; done
      xdpyinfo -display :99 >/dev/null 2>&1
      set +e
      timeout --signal=TERM --kill-after=10s 300s /opt/freecad/AppRun /workspace/tests/freecad_tunic_audit_production.py > /workspace/artifacts/tissu-substep-probe/${substeps}/run.log 2>&1
      status=\$?
      set -e
      printf '%s\n' "\$status" > /workspace/artifacts/tissu-substep-probe/${substeps}/exit-code.txt
      cp -a /workspace/docs/images/generated /workspace/artifacts/tissu-substep-probe/${substeps}/screens
      exit 0
    "
done

python3 - <<'PY'
import json, os
from pathlib import Path

root = Path('artifacts/tissu-substep-probe')
rows = []
for value in (1, 2, 4, 8, 10):
    base = root / str(value)
    status = int((base / 'exit-code.txt').read_text().strip())
    if status not in (0, 1):
        raise SystemExit(f'candidate {value} did not reach the visual gate: status={status}')
    metrics = json.loads((base / 'screens' / 'drape-visual-metrics.json').read_text())
    if any(not panel['finite'] for panel in metrics['panels']):
        raise SystemExit(f'candidate {value} produced non-finite state')
    pngs = list((base / 'screens').glob('cloth-simulation-draped-*.png'))
    if len(pngs) < 7:
        raise SystemExit(f'candidate {value} missing screenshots: {len(pngs)}')
    rows.append({
        'substeps': value,
        'audit_exit': status,
        'visual_gate_passed': status == 0,
        'target_clearance_mm': [panel['target_vertex_clearance'] for panel in metrics['panels']],
        'seam_max_correspondence_gap_mm': metrics['seam_coherence']['max_correspondence_gap_mm'],
    })

summary = {
    'schema': 1,
    'purpose': 'diagnostic-only-tissu-substep-probe',
    'release_gate_effect': 'none',
    'source_head_sha': os.environ['CLOTH_HEAD_SHA'],
    'candidates': rows,
}
(root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
if not any(row['visual_gate_passed'] for row in rows):
    print('tunic-substep-probe=falsified-bounded-range')
else:
    print('tunic-substep-probe=visual-gate-pass-found')
PY

docker run --rm "$FREECAD_TUNIC_IMAGE" bash -lc 'cat /opt/tissu-provenance.txt' > "$root/tissu-provenance.txt"
grep -q '^tissu-source-commit=c28a3c7504ddc782bef844ab5bd4cd0bde14b628$' "$root/tissu-provenance.txt"
grep -q '^tissu-contact-fix-sha256=[0-9a-f]\{64\}$' "$root/tissu-provenance.txt"
grep -q '^tissu-cpp-regression-result=passed$' "$root/tissu-provenance.txt"