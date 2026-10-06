---
applyTo: ".github/workflows/**/*.yml,.github/workflows/**/*.yaml"
---

- Keep one canonical workflow with fail-closed acceptance checks.
- Preserve least privilege and exact PR-head checkout.
- Never run untrusted PR code on privileged self-hosted runners.
- Keep orchestration in `.github/workflows`; Docker/FreeCAD lifecycle belongs in local CI composites.
- Route every FreeCAD acceptance through `.github/actions/freecad-test`.
- Keep hard application budgets and bounded image pulls.
- Prefer matrices for equivalent acceptance cases.
- Main/schedule/trusted manual runs must not be cancelled by newer runs.
- Pull-request runs may cancel superseded work.
- Pin all external Actions to full commit SHAs.
