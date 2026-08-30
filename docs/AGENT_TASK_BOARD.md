# Supervisor task board — 2026-08-30

| Priority | Work | Owner | Dependency | Acceptance |
|---|---|---|---|---|
| P0 | Canonical CI control plane (#293/#294) | Supervisor | none | Jobs schedule; all required CI paths finish |
| P0 | Stale DrapeTarget lifecycle (#289/#292) | Simulation stream | CI | recompute safe; explicit stale reason; refresh gate |
| P0 | Curved/M:N Sewing UX (#275) | Sewing stream | CI | public task panel creates/diagnoses/repairs/saves seam |
| P0 | Canonical garment E2E (#278/#155) | Integration stream | target + sewing | real Pattern→Sewing→Drape→Simulation save/reload cycle |
| P1 | Pattern production audit (#162) | Pattern stream | E2E fixture | native Sketcher authority + semantic marks + invalidation |
| P1 | Avatar target integration (#203/#228) | Fitting stream | target contract | mannequin + arbitrary FreeCAD geometry |
| P1 | Simulation quality (#145) | Simulation stream | stable lifecycle | particle distance/material/collision presets persist |
| P1 | UI consistency (#267) | UX stream | functional gates | coherent task panels/buttons/tooltips |
| P2 | Export/package/solver benchmark | Release stream | all P0/P1 | release package and optional backend comparison |

## Handoff protocol

Each implementation stream must update `AGENT_STATUS.md`, keep its branch isolated, add focused regression coverage, and use the single canonical workflow. No stream is considered complete from utility-only tests.
