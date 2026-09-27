# Agent status

Machine-readable supervisor/recovery record.

## Repository
- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Canonical workflow: .github/workflows/canonical-execution.yml
- Canonical workflow count: exactly one.
- Root experiment ledger: #2492 (FOR SUPERVISOR: Future Goals to ease testing).
- Current production repair state: no Tissu contact fix merged.
- Release-gate thresholds/timeouts/solver budgets remain frozen.

## Recovery policy
- Use #2492 as the single causal ledger.
- One bounded hypothesis per child Issue/PR.
- Reuse existing research/diagnostic infrastructure instead of creating a new workflow or parallel harness.
- A simulation hypothesis is not terminal until the exact-head rendered output has been inspected by a human.
- The governing Issue/PR must contain the actual screenshots inline; an artifact URL alone is not an acceptable visual-review record.
- Preserve falsified hypotheses as concise evidence in #2492; close duplicate implementation lanes with an explicit reason.
- Do not infer a physics fix from scalar clearance/seam/runtime metrics when the rendered garment state disagrees.

## Known reusable work
- #2487: diagnostic contact-controls harness/lifecycle/schema work; retain useful pieces, but do not treat its fixture result as physics evidence.
- #2493: human visual-review artifact retention and intermediate screenshot policy; restore its useful evidence-retention changes.
- #2500/#2503: durable progress and FreeCAD AppRun lifecycle fixes; preserve where already incorporated into current diagnostics.
- #2449/#2450/#2452: BVH ray/parity fixes form a research lineage; preserve as historical evidence rather than reopening duplicates.
- #2476: collider-friction=0.85 experiment is falsified by an unchanged detached/collapsed tunic result.
- #2470/#2466: stitch-compliance=0.001 plumbing/diagnostic lineage is historical evidence, not an accepted product fix.
- #2513/#2515/#2516/#2524: sparse-orientation repair lineage; none is accepted into production.
- #2492 ladder remains the preferred diagnostic path when the current contact hypothesis is falsified.

## Human review requirement
Required simulation review record:
1. exact head SHA and Actions run;
2. actual inline screenshots;
3. observed visual state;
4. comparison with expected state;
5. whether the hypothesis survives;
6. next bounded action.

Never close an unresolved engineering problem solely to reduce queue size.
