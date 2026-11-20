# Exact-tree validation for main README/wiki publication

- Purpose: obtain a successful full-validation run for the exact current `main` source tree, allowing the main-only visual publication workflow to consume matching validated artifacts.
- Base commit at branch creation: `2fa4ee86c76200a984f5d34ea4d1533e87da8b79`.
- Base Git tree: `40e2363bcd1a1ba5fe0cb4c13e13352938671d6b`.
- Current publication failure for the preceding main tree: run [#44734135154](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44734135154) built the pinned PBD image but stopped at exact-tree artifact lookup because no successful full-validation run matched that source tree.
- The current publication run for this base is [#44738453546](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44738453546); its artifact-lookup job is expected to fail until a full-validation run exists for this exact tree.
- Previous successful full-validation run [#44721247215](https://github.com/Uhrendoktor/freecad-cloth/actions/runs/44721247215) passed on a different Git tree and cannot authorize publication of this source tree.
- This record is the sole change in this PR. It changes no application code, workflow, benchmark, solver setting, physical threshold, or generated documentation asset.
- The PR title requests full validation. The resulting `pull_request` run must pass the exact required validation gate for the PR tree.
- Merge only if `main` remains at the recorded base. Use a squash merge that preserves the PR tree exactly. The resulting main push will trigger the existing publication workflow, whose helper can select the successful PR validation run by exact Git-tree equality.
- If `main` advances before merge, update this branch to the latest `main`, update the recorded base/tree, and rerun full validation; do not merge a stale validated tree.
- Keep publication fail-closed. Do not bypass exact-tree comparison or reuse artifacts from a merely similar commit.
