# Exact-head full-validation activation for PR #2847

This note records a new invocation of the repository's guarded main-only rebase broker.

- Target PR: #2847
- Target branch: `feat/layered-outfit-contact-validation`
- Target source head: `a922ac1644ba8de239f186c6a46865623f46ae17`
- Base branch: `main`
- Request: `execution_mode=full` for the exact target PR head.

The preceding exact-head full run failed only on the reusable-workflow 750-line cap and one Ruff formatting difference. Both are corrected on the target head. The broker should perform a no-op rebase (target remains a direct descendant of main) and dispatch full validation again.

This audit note does not change the target PR's Draft state and is not validation evidence.
