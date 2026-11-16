# Exact-head full-validation activation for PR #2847

This is a one-shot activation record for the guarded main-only rebase broker.

- Target PR: #2847
- Target branch: `feat/layered-outfit-contact-validation`
- Integrated head at activation: `2a8eaebc00cfa9efe3219c91bc08b46183b663cf`
- Base: `main`
- Rebase expectation: target head is already a direct child of current `main`, so the broker rebase should be a no-op.
- Validation request: `execution_mode=full` for exact target PR head.

The preceding PR synchronize run is still pending without jobs. This activation uses the repository's canonical main-only `RUN REBASE: PR #<number>` broker to explicitly dispatch full validation. It does not merge or change Draft state on PR #2847. Do not treat this activation record as validation evidence.
