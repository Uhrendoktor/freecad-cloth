# Exact-head full-validation activation for PR #2847 (diagnostic pass)

This note requests the guarded main-only rebase broker to dispatch a fresh full validation run.

- Target PR: #2847
- Target branch: `feat/layered-outfit-contact-validation`
- Target source head: `0c4bbee503cc71bd0995bed8de45f0c942ef6dfd`
- Execution mode: full
- Diagnostic objective: record inter-cloth contact metrics immediately after inter-cloth projection and again after the final mannequin collision projection. No solver parameters, collision thresholds, or acceptance limits are changed.

The previous exact-head run passed strict gates and all matrix jobs except layered-outfit GUI acceptance. The only observed failure was residual cross-garment edge/triangle pairs at checkpoint 1. This retry isolates the projection stage responsible.
