# Canonical CI control-plane notes

The repository uses one canonical workflow: `.github/workflows/canonical-execution.yml`.

A `pull_request` run requires the pull request to have a mergeable result; GitHub does not run `pull_request` workflows while a PR has merge conflicts. Therefore a stale PR is not evidence that the workflow itself is broken. Clean branches created from current `main` are the supervisor's control-plane probe for canonical CI.

The canonical workflow is intentionally not duplicated for probes. Any CI repair must be made in the canonical workflow and verified through a clean PR before being treated as a release gate.

The merged GUI screenshot publisher was reverted to the original non-privileged trigger while its privileged `pull_request_target` variant is separately audited; the publish path must not execute untrusted PR code with write permissions.
