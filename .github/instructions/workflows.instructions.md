---
applyTo: ".github/workflows/**/*.yml,.github/workflows/**/*.yaml"
---

- Keep one canonical workflow and fail-closed acceptance checks.
- Preserve least-privilege permissions and exact PR-head checkout.
- Keep untrusted pull-request code off privileged self-hosted runners.
- Do not introduce parallel workflows or pull_request_target-based brokers.

- Keep `.github/workflows/canonical-execution.yml` as the only event-driven workflow.
- Workflow YAML is orchestration only: FreeCAD Docker lifecycle belongs in `.github/actions/freecad-container`; FreeCAD launches and Xvfb belong in `tools/ci/run_freecad.py`.
- Every FreeCAD acceptance, screenshot, and simulation invocation goes through `.github/actions/freecad-test` and has a maximum application budget of 55 seconds.
- Do not put `docker run`, `docker create`, or `docker cp` in the canonical workflow.
- Prefer matrices for equivalent acceptance cases and independent jobs for expensive visual/simulation cases so hosted jobs retain wall-clock parallelism.
- Main-branch, schedule, and trusted manual runs must not be superseded after starting; only pull-request runs may use cancellation.
- All external Actions referenced by the workflow or local CI composites must be pinned to full commit SHAs.
