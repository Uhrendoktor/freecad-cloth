# Agent status

Machine-readable supervisor/recovery record.

## Repository
- Repository: Uhrendoktor/freecad-cloth
- Default branch: main.
- Canonical workflow: .github/workflows/canonical-execution.yml; exactly one workflow.
- Root experiment ledger: #2492.
- Current main: e3e66e29938d5c71512eec08bc26b2c5a244aa41.
- Production Tissu contact repair: none merged; sparse-orientation lane falsified and retired.
- Active diagnostic critical path: #2481 cube ladder rungs 1-5; stop at first failing rung.
- Active process PR: #2527 screenshot-backed simulation review consolidation.
- Full tunic rendered artifact was human-inspected and shows a visibly collapsed/detached ankle-scale cloth result; it is downstream evidence until the ladder explains the first failure.

## Decisions
- Preserve merged #2487 as diagnostic evidence infrastructure only.
- Do not carry #2516/#2526 sparse-orientation production changes forward.
- Keep solver/collision budgets, thresholds, fixture geometry, seams, pins, placement, workflow topology, and release gates frozen.
- Require exact-head screenshots plus automated artifacts for simulation acceptance.

## Next action
- Finish #2527 process consolidation on current main.
- Finish #2481 exact-head ladder run, inspect every rung/checkpoint, and stop at the first human-visible failure.
