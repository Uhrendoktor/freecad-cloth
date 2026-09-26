# Reproducible Tissu runtime

Canonical GUI simulation uses a source transformed Tissu 1.1.0 runtime because the pinned upstream `MeshCollider::resolve()` implementation derives its collision normal directly from the particle-to-closest-point vector. For a particle that has crossed into a closed mesh, that vector points inward. The repository-controlled source transform corrects that direction only for closed, consistently wound collision surfaces; open/non-manifold meshes retain the legacy behavior.

The canonical provenance is:

- upstream repository: https://github.com/evanrock520-ciencias/Tissu
- pinned source commit: `c28a3c7504ddc782bef844ab5bd4cd0bde14b628`
- base FreeCAD image: `ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3`
- source transform: `tools/patch_pytissu_source.py`

The source transform is built as a wheel in GitHub Actions and passed into the Tissu-backed tunic, turntable, and benchmark jobs as an explicit artifact. The wheel is not copied into the repository or treated as an opaque permanent binary; its build provenance is uploaded beside it.
The build helper normalizes its output directory to an absolute host path before Docker bind mounting, so default and explicit output directories behave identically in CI.

To reproduce the exact runtime locally on a Docker-capable machine:

```bash
tools/build_pytissu_runtime.sh
```

The script fail-closes on an upstream commit mismatch, a source transform-application mismatch, or a failing native `MeshCollider` test. It does not modify any simulation timeout, seam threshold, collision triangle cap, solver quality, or visual acceptance gate.

The host-side post-step containment experiment was rejected separately because it still produced a 50.9 mm tunic seam gap after 90 steps from the validated 8.22 mm fixture. The source-level contact-direction repair therefore targets the earlier, causal failure surface rather than adding another post-step correction heuristic.
No timeout increases are permitted by this integration.
