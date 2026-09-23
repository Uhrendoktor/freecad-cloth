# Tool State

schema: 13
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_issue: 1017
continuation_issue: 1094
active_release_pr: 1096
active_release_branch: supervisor/final-release-fixed-main-20260923
last_audited_main: cf1c75d67cf6be924db10c5a9ba63009ba07ae4e
workflow_count: 1
workflow_image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
validation_policy: preserve_canonical_docker_xvfb_freecad_path; fail_closed_evidence; inspect_jobs_logs_artifacts; no_second_workflow
release_gate:
  candidate: PR_1096
  exact_head: 69215e7286ffda3da655f53094c5ae86d4644eb3
  exact_head_status: no_commit_statuses; no_pull_request_run_visible; prior_push_and_state_sync_runs_failed_pre_job_zero_jobs_zero_artifacts
  timing_fix_pr: PR_1090
  timing_fix_head: 76a37cc9e78a1d810f9c6c116c0d20b14a00124e
  supporting_run: 35845226384
  supporting_artifact: 10743635540
  supporting_run_result: 200_mm_Blanket-over-Cube_real_FreeCAD_Xvfb_acceptance_passed;_16_distinct_motion_frames;_representative_frames_visually_inspected
  external_ci_blocker: current push/pull_request Actions delivery is failing before job allocation; connector exposes no workflow-dispatch operation and no Actions policy administration
final_gate: exact_head_canonical_pr_green; inspect_jobs_logs_artifacts; merge; merged_main_canonical_pr_green; fresh_repo_audit
open_actionable_issues: [1017, 1020, 1043, 1053, 1084, 1088, 1090, 1094]
remote_branch_count_observed: 497
last_schedule_run: 3225/35839191664; success; 12 jobs instantiated; daily retention job skipped because event was the */5-minute schedule
published_asset_gap: docs/screenshots:docs/images/generated/cloth-blanket-motion.gif
duplicate_release_prs_closed: [1093, 1095]
duplicate_timing_prs_closed_unmerged: [1089, 1091, 1092]