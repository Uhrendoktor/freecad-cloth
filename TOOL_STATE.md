# Tool State

```yaml
schema: 7
repository: Uhrendoktor/freecad-cloth
canonical_workflow: .github/workflows/canonical-execution.yml
execution_policy: ADVANCED_TOOL_MODE.md in Uhrendoktor/GPT-ToolsAndStorage
supervisor_task: #647 release lifecycle closeout
current_main: 60393fecbee814f56ed8018f648167eb461e9c0b
open_prs: []
open_actionable_issues: [647, 720, 471]

architecture:
  package_root: freecad_cloth/
  domain_packages: [avatar, pattern, sewing, simulation]
  shared_packages: [common, shared]
  root_python: [Init.py, InitGui.py, sitecustomize.py]
  drape_target_owner: freecad_cloth.simulation.DrapeTarget
  diagnostics_owner: freecad_cloth.common.ClothDiagnostics
  semantic_boundaries: [PatternIR, SewingGraph, SimulationScene, DrapeTarget]
  policy: FreeCAD_owns_geometry_and_persistence; Cloth_owns_garment_semantics; solver_owns_physics; derived_simulation_state_is_rebuildable_and_invalidated

workflow_contract:
  workflow_count: 1
  workflow: .github/workflows/canonical-execution.yml
  image: ghcr.io/uhrendoktor/freecad-cloth/freecad-ci:freecad-1.1.0-py312-r3
  screenshot_display: 1280x720
  screenshot_artifact: tunic-visual-audit
  turntable_artifact: readme-turntables
  policy: preserve_Docker_Xvfb_FreeCAD_path; fail_closed_evidence; no_second_workflow

latest_verified_ci:
  run_id: 35814799483
  run_number: 3084
  commit: fa1df9f498ecfdcbd2f56c363e30ed7d28d700dd
  pr: 1009
  status: completed
  conclusion: success
  jobs:
    - Python and FreeCAD non-GUI tests
    - Full tunic visual and simulation audit
    - Sewing staged creation smoke
    - Pattern production export smoke
    - README turntables
  skipped_on_pr:
    - Measured FreeCAD workbench benchmark
    - Publish README turntables
  artifacts:
    tunic_visual_audit_id: 10731790123
    tunic_visual_audit_sha256: 267405a507a1ee33d806266bedb61f44cd99995ed2510af77d31eec7f4a8a357
    sewing_creation_smoke_id: 10731420436
    sewing_creation_smoke_sha256: 09c6f69de9f2fb3d400f6aeee8c12d1244bb1ec1b3dda4ef6fd272992d1fc31a
    pattern_export_id: 10730914887
    pattern_export_sha256: cc06fb1d57044e77593e0999c873b687b7c1a2b634074698be981ee881126de4
    readme_turntables_id: 10731555405
    readme_turntables_sha256: a526ac4e79b805addcd374e93eee1ece2f92e1a7521a54ab1b27f82ef437158c

release_evidence:
  garment_e2e: passed
  sewing_curved_mn: passed
  arrangement: passed_pieces_4
  garment_hierarchy: passed
  drape_target: passed_mannequin
  diagnostics: passed_stress
  save_reload: passed
  invalidation_and_repair: passed
  stale_export: blocked
  deterministic_rerun: passed
  pattern_export: passed_SVG_DXF
  canonical_visuals: six_drape_views_plus_diagnostics
  drape_metrics:
    front: finite=true; connected_components=1; state=structurally-plausible; target_vertex_clearance_mm=4.0799
    back: finite=true; connected_components=1; state=structurally-plausible; target_vertex_clearance_mm=1.0594
  seam_coherence:
    max_correspondence_gap_mm: 20.842179
    method: solver-stitch-pairs
    mode: diagnostic_only

historical_closeout:
  merged_release_pr: 1001
  merged_release_commit: 2b09ea32426d8f26141c4a0d8e9c294509e29893
  current_main_has_release: true
  sewing_closeout_issue: 475_closed_completed
  stale_runner_prs: [904_closed, 925_closed, 1008_closed]
  stale_curved_sewing_pr: 999_closed
  lifecycle_issues_closed: [1002, 1004, 1005, 1006, 987, 917, 837, 893, 828, 845, 692, 675]

policy:
  - inspect_open_prs_and_issues_before_changes
  - one_canonical_workflow
  - terminal_green_ci_before_dependent_merge_or_close
  - inspect_artifacts_and_logs
  - never_weaken_validation
  - close_issues_only_with_explicit_state_reason
  - re_cut_implementation_branches_from_current_main
```
