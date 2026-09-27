# Simulation visual review protocol

This repository treats rendered simulation output as first-class evidence.

## One hypothesis per review

Each simulation review belongs to one bounded causal experiment recorded under root issue #2492. The implementation may change only the variable named by the hypothesis. Solver budgets, collision budgets, thresholds, timeouts, fixture geometry and workflow topology remain frozen unless #2492 explicitly records a new causal question.

## Required evidence

The governing Issue or PR must show the actual screenshots inline in the GitHub conversation. Do not rely only on CI logs or an artifact download link.

For a one-step diagnostic, show the initial and post-step frames.

For the #2492 complexity ladder, show the checkpoint frames requested by the rung. For garment-scale runs, show intermediate simulation checkpoints plus front/rear/right/left/top/bottom final views.

The evidence must identify the exact head SHA and Actions run. The screenshot set must come from that exact execution.

## Human observation format

Record:
- what is visibly attached, detached, penetrating, collapsed, drifting, or otherwise incorrect;
- which step first shows the visible failure;
- whether the failure is already present in the initial frame;
- whether the visible result changed in the direction predicted by the hypothesis.

Do not substitute a metric for the rendered observation. Metrics explain the image; they do not replace it.

## Falsification and salvage

When a hypothesis is falsified, add a concise evidence entry to #2492 and close its duplicate child lane with the factual reason. Reuse useful code, tests, harness improvements, and regression fixtures in the next authoritative branch, but do not carry an unproven production physics modification forward merely because it already exists in a closed PR.

## Current causal ladder

The shared #2492 ladder remains:

1. single piece / cube / pinned
2. single piece / cube / unpinned
3. two pieces / cube / no seam
4. two pieces / cube / one small-span seam
5. two pieces / cube / one large-span seam
6. single piece / avatar / supported
7. single piece / avatar / unsupported
8. two pieces / avatar / no seam
9. two pieces / avatar / small-span seam
10. two pieces / avatar / production-scale seam span
11. production-like two-piece avatar / correct near-zero seam launch
12. full tunic

Stop at the first failing rung. Do not interpret later rungs until the first failure has a human-visible explanation.
