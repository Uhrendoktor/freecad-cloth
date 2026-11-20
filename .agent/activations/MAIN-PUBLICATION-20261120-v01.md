# Exact-tree validation for main README/wiki publication

- Purpose: obtain a successful full-validation run for the exact source tree currently on `main`, so the main-only visual publication workflow can consume validated artifacts without relaxing its exact-tree gate.
- Base commit at branch creation: `83a5ada08a4cf29643de669324f24c5e2d7c17af`.
- Base Git tree: `effce315f1ab478825b0fd972f596800d1c42d21`.
- Current publication failure: run [#44734135154](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44734135154) successfully built the pinned PBD image but stopped at exact-tree artifact lookup: no successful full-validation run matched `effce315f1ab478825b0fd972f596800d1c42d21`.
- Prior full-validation run [#44721247215](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44721247215) passed on a different Git tree and cannot authorize publication of this source tree.
- This record is the sole change in this PR. It changes no application code, workflow, benchmark, solver setting, physical threshold, or generated documentation asset.
- The PR title requests full validation. The resulting `pull_request` run must pass the exact required validation gate for the PR tree.
- Merge only if `main` has not advanced from the recorded base. Use a squash merge that preserves the PR tree exactly. The resulting main push will trigger the existing publication workflow, whose helper can select the successful PR validation run by exact Git-tree equality.
- If `main` advances before merge, update this branch to the latest `main`, record the new base/tree, and rerun full validation; do not merge a stale validated tree.
- Keep publication fail-closed. Do not bypass exact-tree comparison or reuse artifacts from a merely similar commit.
