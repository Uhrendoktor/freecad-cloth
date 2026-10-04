from pathlib import Path
import re

def load(p): return Path(p).read_text(encoding="utf-8")
def save(p,s): Path(p).write_text(s,encoding="utf-8")
def rename(s):
    return (s.replace("pytissu","pyPBD")
      .replace("CLOTH_TISSU_","CLOTH_PBD_")
      .replace("CLOTH_CI_ENABLE_TISSU","CLOTH_CI_ENABLE_PBD")
      .replace("CLOTH_CI_DISABLE_TISSU","CLOTH_CI_DISABLE_PBD")
      .replace("FREECAD_TISSU_IMAGE","FREECAD_PBD_IMAGE")
      .replace("TISSU","PBD")
      .replace("TissuBackend","PositionBasedDynamicsBackend")
      .replace("Tissu","PositionBasedDynamics")
      .replace("tissu","pbd"))

for p in ["README.md","docs/ARCHITECTURE.md","docs/BACKEND_EVALUATION.md","docs/INSTALLATION.md","docs/DEVELOPMENT.md","docs/LIBRARY_EVALUATION.md"]:
    save(p,rename(load(p)))

s=load("AGENT_STATUS.md")
s=s.replace(
    "The current Tissu tunic behavior remains under diagnostic investigation in #2492; do not infer that current simulation behavior is green from older release-closeout prose or screenshots.",
    "The current PositionBasedDynamics runtime is authoritative. Historical Tissu diagnostic lanes and older release-closeout screenshots are context only; do not infer current simulation behavior from them.")
save("AGENT_STATUS.md",s)

d=load("docs/DECISIONS.md")
if "D-0003 — PositionBasedDynamics is the sole production runtime solver" not in d:
    save("docs/DECISIONS.md",d+"""
## D-0003 — PositionBasedDynamics is the sole production runtime solver

Date: 2026-10-04  
Status: accepted  
Supersedes: D-0002

The production cloth runtime is now the native PositionBasedDynamics Python binding (pyPBD==2.2.2). The existing ClothBackend adapter contract and headless ClothSystem input model remain solver-neutral. PositionBasedDynamics owns integration, XPBD cloth/stretch/shear constraints, XPBD bending, sewing distance constraints, pin masses, and DrapeTarget mesh collision. The canonical FreeCAD CI image preinstalls the pinned wheel; runtime code never installs or patches the solver.

The migration keeps the persistent DrapeTarget / CollisionSurface boundary, the one-backend architecture, deterministic rebuild semantics, and the canonical GUI acceptance path. Tissu remains historical evidence only and is no longer a runtime dependency.
""")

save("pyproject.toml",load("pyproject.toml").replace("pytissu==1.1.0","pyPBD==2.2.2"))
save("pyrightconfig.json",load("pyrightconfig.json").replace("freecad_cloth/simulation/TissuBackend.py","freecad_cloth/simulation/PositionBasedDynamicsBackend.py"))

for p in [
    "freecad_cloth/simulation/SimulationObjects.py",
    "freecad_cloth/simulation/SimulationQualityRuntimeV2.py",
    "freecad_cloth/simulation/RealtimePreview.py",
    "freecad_cloth/simulation/ClothBackend.py",
    "freecad_cloth/simulation/ClothSolver.py",
]:
    save(p,rename(load(p)))

site='''"""FreeCAD CI compatibility shims loaded before test scripts."""
try:
    from PySide6 import QtGui
except ImportError:
    QtGui = None
if QtGui is not None:
    QPixmap = QtGui.QPixmap
    if not hasattr(QPixmap, "pixel"):
        def _pixel(self, x, y): return self.toImage().pixel(x, y)
        QPixmap.pixel = _pixel
import os
def _require_pbd():
    try:
        import pypbd  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("PositionBasedDynamics CI mode requires pyPBD") from exc
def _install_pbd_backend_hook():
    from freecad_cloth.simulation.PositionBasedDynamicsBackend import PositionBasedDynamicsBackend
    from freecad_cloth.simulation.SimulationQualityRuntimeV2 import QualitySimulationProxy
    original_execute = QualitySimulationProxy.execute
    if getattr(original_execute, "_cloth_pbd_enforced", False): return
    def execute(self, obj):
        result = original_execute(self, obj)
        backend = getattr(self._base_or_restore(), "backend", None)
        if not isinstance(backend, PositionBasedDynamicsBackend):
            raise RuntimeError("canonical GUI simulation did not select PositionBasedDynamics")
        print("cloth-ci-backend=position-based-dynamics", flush=True)
        return result
    execute._cloth_pbd_enforced = True
    QualitySimulationProxy.execute = execute
if (os.environ.get("DISPLAY") == ":99"
    and os.environ.get("CLOTH_CI_ENABLE_PBD","0") == "1"
    and os.environ.get("CLOTH_CI_DISABLE_PBD","0") != "1"):
    _require_pbd()
    os.environ["CLOTH_SIMULATION_BACKEND"]="position-based-dynamics"
    os.environ.setdefault("CLOTH_PBD_SUBSTEPS","1")
    _install_pbd_backend_hook()
'''
save("sitecustomize.py",site)

save("docker/freecad-ci/Dockerfile",'''FROM ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN /opt/conda/envs/freecad/bin/python -m pip install --no-cache-dir \
        pypbd==2.2.2 \
        triangle==20250106 \
        pytest \
    && /opt/conda/envs/freecad/bin/python -c "import importlib.metadata, pypbd; print("''+"pypbd="+''+''\' + importlib.metadata.version("pyPBD")); print("''+"pypbd_module="+''+''\' + pypbd.__file__)" \
    && cat > /opt/pypbd-provenance.txt <<'EOF'
Package: pyPBD
Version: 2.2.2
Import: pypbd
Wheel: pypbd-2.2.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
SHA256: a5147c9c73e6f51e2963f664e90336a8813a4b37f19c2c20369e5b1ddad59834
EOF

ENV PYTHONPATH=/workspace
''')

for p of Path("tests").glob("*.py"):
    save(p,rename(load(p)))

p=Path("tests/test_tunic_audit_contract.py")
c=rename(load(p))
new='''def test_pbd_ci_image_is_pinned_and_preinstalled():
    dockerfile = (ROOT / "docker" / "freecad-ci" / "Dockerfile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "canonical-execution.yml").read_text(encoding="utf-8")
    assert "pypbd==2.2.2" in dockerfile
    assert "triangle==20250106" in dockerfile
    assert "/opt/pypbd-provenance.txt" in dockerfile
    assert "pbd_validation_image:" in workflow
    assert "FREECAD_PBD_IMAGE" in workflow
    assert "CLOTH_CI_ENABLE_PBD=1" in workflow
'''
c,n=re.subn(r"(?ms)^def test_pbd_ci_image_is_pinned_and_self_regressing():.*?(?=^def )",new,c,count=1)
if n!=1: raise SystemExit("old Tissu image contract not found")
save(p,c)

for old,new in {
    "tests/freecad_tun​ic_audit_tissu.py":"tests/freecad_tunic_audit_pbd.py",
    "tests/freecad_tissu_contact_diagnostics.py":"tests/freecad_pbd_contact_diagnostics.py",
    "tests/freecad_tissu_cube_ladder.py":"tests/freecad_pbd_cube_ladder.py",
    "tests/freecad_tissu_avatar_ladder.py":"tests/freecad_pbd_avatar_ladder.py",
    "tests/test_tissu_contact_diagnostics_contract.py":"tests/test_pbd_contact_diagnostics_contract.py",
    "tests/test_tissu_cube_ladder_contract.py":"tests/test_pbd_cube_ladder_contract.py",
    "tests/test_tissu_avatar_ladder_contract.py":"tests/test_pbd_avatar_ladder_contract.py",
}.items():
    old_path,new_path=Path(old),Path(new)
    if old_path.exists(): old_path.rename(new_path)

patch=Path("docker/freecad-ci/apply-tissu-contact-fix.py")
if patch.exists(): patch.unlink()

w=rename(load(".github/workflows/canonical-execution.yml"))
w=re.sub(r"
  # AGENT-REFactor-BEGIN.*?
  # AGENT-REFactor-END
?","
",w,flags=re.S)
save(".github/workflows/canonical-execution.yml",w)

if Path("tools/agent_pbd_migrate.py").exists(): Path("tools/agent_pbd_migrate.py").unlink()
stale=[p.as_posix() for p in Path("freecad_cloth/simulation").glob("*.py") if "tissu" in p.name.lower()]
if stale: raise SystemExit("stale runtime modules: "+",".join(stale))
print("positionbaseddynamics-migration=ready")
