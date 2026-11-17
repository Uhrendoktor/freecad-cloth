# Explicit PR Rebase and Full Validation

The canonical execution workflow supports an exact-head full-validation activation for a same-repository pull request whose branch must first be rebased onto the latest `main`.

## Activation

1. Open a small, reviewable pull request targeting `main` for the maintainer change that needs the rebase/validation run.
2. Squash-merge that pull request with the exact commit title `RUN REBASE: PR #<number>`, replacing `<number>` with the target pull request number.
3. The `guarded-rebase-pr` job in `.github/workflows/canonical-execution.yml` validates that the target is open, based on `main`, and hosted in this repository. It checks the branch head has not changed, rebases it onto the current `main`, and pushes with a force-with-lease.
4. The same job dispatches `commit-validation.yml` in `full` mode for the rebased head SHA and target PR number.

The activation job refuses stale branch observations and stops on rebase conflicts. Resolve conflicts in the target PR branch and repeat the activation; do not bypass the check with a direct write to protected `main`.

## Validation result

A queued run is not a validation result. Verify that the dispatched run's head SHA matches the rebased PR head, all required jobs completed successfully, and any GUI acceptance artifacts were inspected before marking the PR ready or merging it.
