# Tool State

```yaml
schema: 12
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1094
active_release_pr: 1093
active_release_branch: supervisor/release-candidate-69215e7-recovery-20260923
current_main: b543fb5198616984f70d76261ba825a682d7f92a
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1093
  exact_head: 69215e7286ffda3da655f53094c5ae86d4644eb3
  pr_run_state: no pull_request run/status after fresh open/close/reopen probe; latest exact-head push run #3507 / 35879364633 failed pre-job with zero jobs/artifacts
  candidate_relation_to_main: ahead_by_2; behind_by_6; behind side is subsequent supervisor/documentation history and must not be rebased away before exact-head validation
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200 mm Blanket-over-Cube real FreeCAD/Xvfb acceptance passed; 16 distinct motion frames and representative checkpoints inspected
  external_ci_blocker: exact-head pull_request delivery remains absent and push attempts fail before job allocation; connector exposes no workflow dispatch or Actions policy administration
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1084, 1088, 1092, 1093, 1094]
remote_branch_count_observed: 497
last_schedule_run: 3225/35839191664; success; 12 jobs instantiated; daily retention job skipped because event was the */5-minute schedule
published_asset_gap: docs/screenshots:docs/images/generated/cloth-blanket-motion.gif
duplicate_issue_closed: 1085
duplicate_timing_prs_closed_unmerged: [1090, 1091]
readme_gif_timing_fix_pr: 1092
readme_gif_timing_fix_head: e92d796bcd8bada1b7c27e887121ad1f16049cac
readme_gif_timing_fix_ci: no pull_request workflow run/status delivered
```

closed_research_issues: [1042, 1055]
stale_branch_cleanup: unavailable_via_current_connector; current full branch pagination observes 497 remote branches; no fresh daily 03:00 UTC retention run evidenced
