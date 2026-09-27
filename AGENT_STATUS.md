# Agent status

Machine-readable supervisor/recovery record. Durable guidance lives in docs/DEVELOPMENT.md and #2492.

## Repository
- Repository: Uhrendoktor/freecad-cloth
- Default branch: main
- Current main: dc1feac2d7d80b13a5afb5176164c016a05dd88a
- Canonical workflow: .github/workflows/canonical-execution.yml; exactly one workflow.
- Root experiment ledger: #2492.
- No production Tissu contact repair is merged.

## Active diagnostic lanes
- #2537 / #2481 successor: cube complexity ladder rungs 1-5.
- #2482: avatar complexity ladder rungs 6-10.
- #2535: tunic initial/first-step collision penetration.
- #2540: canonical tunic stitch rest-state at Tissu handoff.

## Superseded coordination
- #1347 is closed as duplicate of #2492.
- #2493 and #2527 are superseded by merged #2541.
- #2516 and #2524 are retired production-contact hypotheses.
- #2481 is superseded by #2537.

## CI / evidence contract
- #2541 merged the screenshot-first review protocol and inline evidence publisher.
- #2542 merged the permissions/authentication fix required for persistent evidence publication.
- Simulation acceptance requires exact-head rendered screenshots in the governing PR/issue conversation; artifact links and scalar metrics are secondary.
- The canonical workflow remains the sole CI workflow and its release-gate topology is unchanged.

## Supervisor rule
One hypothesis, one active implementation PR, one falsifier. Preserve failing screenshots and historical findings; do not revive duplicate implementation lanes without a new causal question.