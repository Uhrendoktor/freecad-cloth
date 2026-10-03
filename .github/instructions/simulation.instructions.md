---
applyTo: "freecad_cloth/simulation/**/*.py,tests/freecad_*.py,docs/SIMULATION_REVIEW.md"
---

- Keep document-persistent state as authority; solver state is derived and rebuildable.
- Production simulation changes require exact-head regression evidence and the canonical GUI path when applicable.
- Diagnostic-only controls must remain outside release-gate acceptance.
- Use one bounded hypothesis and one falsifier; historical issue text is evidence, not implementation authority.
