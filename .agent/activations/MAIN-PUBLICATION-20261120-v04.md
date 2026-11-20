# Exact-tree validation for main README/wiki publication

- Purpose: create a successful full-validation run for the exact current `main` source tree so the main-only README/wiki publication workflow can select matching validated evidence.
- Current main base SHA: `48c4b87c70e3bbf7d7dfea217abff4e5c5c4c6ad`.
- Current main Git tree: `0c9a68fc8f8fc143d642792e3b599b2ddf31415c`.
- Main publication run [#44758436299](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44758436299) successfully built the pinned PBD image and completed the main-only PR rebase step, but stopped at the exact-tree artifact lookup because no successful full-validation run matched this source tree.
- Previous full-validation runs on earlier main trees are not valid evidence for this tree.
- This PR changes only this activation-record file; no application, workflow, benchmark, solver, physical threshold, or generated visual asset is changed.
- Its `pull_request` run must pass the exact `Full validation (explicit request) / Required validation gate` on the resulting PR head.
- Before merging, recheck that main is still at the base SHA above. Merge without changing the tested PR tree, then verify the ensuing main-publication run finds the validation run by exact Git-tree equality and publishes README/wiki visual evidence.
- If main advances before the full run completes or before merge, rebase this branch to the new main tree and rerun validation. Do not reuse a merely similar or ancestor tree.
- Keep the artifact lookup fail-closed; do not alter provenance matching, retries, or gate requirements.
