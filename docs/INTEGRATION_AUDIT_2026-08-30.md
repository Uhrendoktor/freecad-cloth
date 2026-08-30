# Cloth Workbench Integration Audit — 2026-08-30

## Scope

Audit the public product journey:

`Pattern creation -> parametric editing -> pattern validation -> sewing -> seam diagnostics -> avatar -> arrangement -> DrapeTarget -> simulation -> draped result -> save -> reload -> modify pattern -> stale-target detection -> refresh -> simulation again`.

The audit deliberately distinguishes integration defects from feature-scope defects. No isolated feature implementation was added.

## Evidence reviewed

- Mainline `AGENT_STATUS.md`, canonical workflow and current public workbench registrations.
- Open feature PRs, especially Pattern native validation (#300) and Sewing hardening (#296).
- Existing `tests/freecad_smoke.py` and `tests/freecad_e2e.py`.
- DrapeTarget, Simulation, Avatar and fitting command/document-object contracts.

## Findings

### 1. DrapeTarget GUI creation could demote the target to the legacy AvatarProxy path — fixed

`DrapeCommands._attach_to_simulation()` called `set_avatar_collision_source()`. That compatibility function updates/returns `AvatarProxy`, and its target assignment uses `Mannequin`. A user selecting arbitrary FreeCAD Shape/Mesh geometry through the public DrapeTarget command could therefore lose the requested `FreeCAD Geometry` target semantics at the simulation link boundary.

**Fix:** GUI target commands now assign `scene.DrapeTarget` directly and preserve the requested target type. `AvatarProxy` remains compatibility state.

### 2. Refresh existed as a Python service but not as a public workbench action — fixed

`DrapeTarget.refresh_drape_target()` existed, but the Simulation workbench exposed no refresh command and its task panel did not expose target state. After an upstream pattern/source change, the user could reach a stale target without a visible recovery path.

**Fix:** add `ClothDrape_RefreshTarget`, show target status in the Simulation task panel, and expose a Refresh Drape Target control.

### 3. Simulation command enablement ignored target staleness — fixed

Step/Run were enabled whenever a simulation object existed. The simulation proxy correctly rejected stale targets, but the failure happened only after command activation/recompute.

**Fix:** Step/Run activation now requires a current DrapeTarget, and the task panel disables both controls while the target is stale/unbuilt.

### 4. AvatarProxy return/link contract was broken — fixed

`set_avatar_collision_source()` updated `scene.AvatarProxy` but returned the `DrapeTarget`. Callers such as avatar/fitting integration assigned that return value to compatibility links, creating a broken semantic link: a property named `AvatarProxy` could point at `DrapeTarget`.

**Fix:** the compatibility setter returns the actual `AvatarProxy` while continuing to update the authoritative `DrapeTarget` as a side effect.

### 5. Seam repair broad exception hides root causes — tracked outside integration scope

`SewingCommands.repair_selected_seam()` catches `Exception` around seam length/object lookup and converts it into a generic error. This can conceal broken links or unexpected geometry failures.

Tracked in **#301**; no feature-layer implementation was duplicated in this audit.

### 6. Canonical E2E does not yet exercise the complete requested journey — existing release blocker

Current `tests/freecad_e2e.py` covers native Pattern/Sewing/Simulation creation plus save/reload and upstream edit invalidation, but it does not yet exercise the requested pattern-validation UI, persistent avatar arrangement, DrapeTarget refresh loop, and all public command/task-panel transitions as one scenario.

This is already the purpose of **#278**, so no duplicate issue was created.

Pattern validation is supplied by open **PR #300** and was not reimplemented here.

## Journey status

| Journey step | Audit status |
|---|---|
| Pattern creation | implemented/public command path exists |
| Parametric editing | implemented/public task-panel/Sketcher path exists |
| Pattern validation | **blocked on PR #300 landing + canonical E2E coverage** |
| Sewing | implemented/public commands and task panel exist |
| Seam diagnostics | implemented; broad exception follow-up #301 |
| Avatar | implemented/public Sewing workbench commands exist |
| Arrangement | implemented as persistent fitting document state; full public E2E coverage remains #278 |
| DrapeTarget | authoritative after PR #303 integration fixes |
| Simulation | implemented; stale-target execution now blocked |
| Draped result | implemented by simulation proxy |
| Save/reload | existing E2E coverage exists; final public journey coverage remains #278 |
| Modify pattern | existing invalidation path exists |
| Stale-target detection | implemented and exposed in status |
| Refresh | now public command/task-panel action in PR #303 |
| Simulation again | command/task panel now re-enable only after target refresh |

## Release decision

**Not release-ready from this audit alone.** The integration defects are addressed in PR #303, but the complete public-workbench acceptance scenario remains a release gate in #278 and Pattern validation remains dependent on PR #300.

Canonical CI is the acceptance mechanism; no additional workflow is introduced.
