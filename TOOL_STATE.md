# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1086
active_release_pr: 1093
active_release_branch: supervisor/release-candidate-69215e7-recovery-20260923
current_main: 1b9af2dd8bb6554fcefcf30f0d723ae46fac9a65
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1093
  exact_head: 69215e7286ffda3da655f53094c5ae86d4644eb3
  pr_run_state: PR_1093 exact head 69215e7286ffda3da655f53094c5ae86d4644eb3 has no pull_request run/status; timing-fix PR_1090 head 76a37cc9e78a1d810f9c6c116c0d20b14a00124e has no pull_request run/status
  candidate_relation_to_main: ahead_by_2; behind_by_5; behind commits are supervisor-state/documentation updates; preserve exact head until validation
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200 mm Blanket-over-Cube real FreeCAD/Xvfb acceptance passed; 16 distinct motion frames and representative checkpoints inspected
  external_ci_blocker: current push/pull_request Actions delivery is failing before job allocation; connector exposes no workflow-dispatch operation and rejects required Actions administration-policy endpoints
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1084, 1086, 1088]
remote_branch_count_observed: 491
last_schedule_run: 3225/35839191664; success; 12 jobs instantiated; daily retention job skipped because event was the */5-minute schedule
published_asset_gap: docs/screenshots:docs/images/generated/cloth-blanket-motion.gif
duplicate_issue_closed: 1085
duplicate_timing_prs_closed_unmerged: [1091, 1092]
readme_gif_timing_fix_pr: 1090
readme_gif_timing_fix_head: 76a37cc9e78a1d810f9c6c116c0d20b14a00124e
readme_gif_timing_fix_ci: run_3529_35904255064_zero_jobs_zero_artifacts
```

closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector; current full branch pagination observes 491 remote branches; no fresh daily 03:00 UTC retention run evidenced
