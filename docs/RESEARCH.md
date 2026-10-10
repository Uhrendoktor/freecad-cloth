# CLO-style research and feature model

This document is a durable design-research summary, not a current implementation or release-status record. Verify implementation claims against the current branch and current-state records.

## Product boundary

The target is a FreeCAD-native garment workflow with CLO-like interactions, not a clone of proprietary internals.

`Pattern → Sewing → Arrange/Fit → Simulate → Diagnose → Output`

FreeCAD owns editable geometry and document persistence. Cloth owns garment semantics. The solver owns physics. Derived mesh, collision and numerical state are rebuildable.

## Common sewing workflow

Commercial garment tools treat sewing as an explicit, transactional operation rather than an incidental geometry constraint. The useful baseline is:

- Segment Sewing and Free Sewing;
- 1:N, M:1 and M:N relationships;
- selectable ranges on edges/curves;
- explicit orientation/reversal;
- length-aware correspondence diagnostics;
- staged selection with commit/cancel and recovery;
- notches/direction indicators that communicate correspondence;
- persistent seam objects independent of generated mesh topology.

For FreeCAD, these belong in Cloth Sewing. Sketcher constraints remain geometric constraints, not physical seams.

## Pattern-production workflow

A practical garment pattern workflow also needs, in increasing maturity:

- seam allowance with persistent parameters and validation;
- notches and grainlines;
- internal marks, darts, folds and construction annotations;
- measurement-driven dimensions and expressions;
- grading and multi-size review;
- deterministic DXF/SVG/TechDraw output;
- plotting/print layout;
- later nesting and manufacturing validation.

These should be semantic Pattern data and adapters around native FreeCAD geometry, not a second drafting kernel.

## Fitting and simulation workflow

Fitting is more than moving a mesh once. Useful persistent concepts are arrangement points/anchors, wrap direction, superimpose, reset, body measurements and a named collision target. Simulation then adds mesh quality, material parameters, pinning, solver controls and diagnostics.

Particle distance/resolution is a real quality/performance control. Material data should include density/thickness and stretch/shear/bending/friction where the reference solver can use them. Changing these inputs invalidates derived simulation state.

## Avatar strategy

Use one target-neutral interface:

```text
                 DrapeTarget
                /           \
      Human Mannequin     FreeCAD Geometry
      AvatarService        Shape/Body/Mesh
                \           /
                 CollisionSurface
                       |
                   Simulation
```

The deterministic native mannequin is the release baseline for the documented release slice. A higher-fidelity generated/imported human body is a later provider, not a prerequisite and not a new solver path. Current implementation status must be taken from the current repository, not this design summary.

## UI/UX model

Every task panel should answer, in order:

1. What am I editing and is it valid?
2. What is the next primary action?
3. What reversible/inspection actions are available?
4. Which persistent parameters can I change?
5. How do I recover from stale or invalid state?

Use Preview → Apply for multi-parameter fitting changes. Keep selection highlights, transient previews and task-panel state separate from persistent document authority.

## Release order

### Prototype
Prove the boundaries with a small multi-piece garment, transactional sewing, deterministic arrangement, one mannequin and one generic target, preview mesh, CPU reference drape, save/reload and invalidation.

### MVP
Harden semantic references/topology repair, curved correspondence, 1:N/M:N/free sewing, arrangement points, mannequin measurements/poses, generic targets, material/quality presets, pinning and production-oriented 2D output.

### Production
Add higher-fidelity avatar providers, richer collision targeting, fit/stress/strain/pressure maps, grading/nesting/manufacturing validation, advanced construction and optional solver benchmarks.

## FreeCAD mapping

| Need | Prefer native FreeCAD | Cloth layer |
|---|---|---|
| Pattern geometry | Sketcher + Part/OCCT | PatternPiece identity/semantics |
| Constraints | Sketcher constraints/Expressions | Measurement helpers |
| Persistence | DocumentObject, Links, Groups, Placement, recompute | Stable semantic references/invalidation |
| Mesh | Mesh/MeshPart | PatternIR/mesh adapter |
| Production pages | TechDraw/Draft | Garment layers/annotations/export orchestration |
| 3D target | Part/PartDesign/Mesh | DrapeTarget provider |
| Physics | deterministic CPU reference first | solver adapter + material/quality contract |

## Research references

Primary references used for workflow decisions:

- CLO Help Center: 3D Sewing, Segment Sewing, Free Sewing, M:N sewing, Particle Distance, Auto Sewing, Auto Fitting, Set Grading.
- FreeCAD documentation/source: Sketcher SketchObject, Sketcher constraints, TechDraw workbench/API.
- Style3D documentation/workflows: curved pattern authoring, sewing, simulation quality and DXF interchange.
- Seamly2D: measurement-driven drafting and size-parametric patterns.
- Optitex and comparable production tools: fit/tension analysis and manufacturing-oriented pattern workflows.

Specific URLs are intentionally kept here rather than repeated across multiple dated research notes. Verify current vendor documentation before treating a feature as a compatibility promise.


## Avatar Pose Mode UI research

The merged FK skeleton should be edited as a pose tool rather than as a list of
Euler-value fields.

- Blender Pose Mode establishes the viewport-first model: click a bone/joint,
  use the gizmo rings for axis-specific rotation, use the trackball for free
  rotation, and use X-Axis Mirror for bilateral posing. Snapping/precision can
  be temporary interaction aids rather than permanent numeric inputs.
  References:
  https://docs.blender.org/manual/en/latest/editors/3dview/display/gizmo.html
  https://docs.blender.org/manual/en/latest/editors/3dview/controls/snapping.html
  https://docs.blender.org/manual/en/latest/editors/3dview/controls/transform/transform_control/precision.html
- CLO 3D's Adjust Avatar Joints uses FK joint adjustment with a Gizmo and a
  dedicated symmetric control. Its workflow also separates direct joint
  manipulation from broader IK workflows.
  Reference:
  https://support.clo3d.com/hc/en-us/articles/360000013808-Adjust-Avatar-Joints
- Marvelous Designer uses a Unified Gizmo for rotate/move operations and exposes
  X-ray avatar joints, supporting a model where the skeleton is directly
  selectable in the 3D view rather than only through a property panel.
  References:
  https://support.marvelousdesigner.com/hc/en-us/articles/47358262924185-Adjust-Avatar-Pose
  https://support.marvelousdesigner.com/hc/en-us/articles/47358262924185
- Style3D adds bilateral skeleton linkage and joint-angle limits. Angle limits are
  a useful future layer for Cloth, but this PR deliberately does not invent
  anatomical limits that are absent from the current skeleton data contract.
  Reference:
  https://help.style3d.com/studio/en/1f8f/39dc
- FreeCAD exposes the Coin3D scene graph and Pivy event callbacks needed to place
  a transient posing overlay without adding another geometry engine.
  The Coin SoTrackballDragger provides three principal-axis bands plus free-form
  trackball rotation and start/motion/finish callbacks.
  References:
  https://reqrefusion.github.io/FreeCAD-Documentation-html/wiki/en/Code_snippets.html
  https://www.coin3d.org/coin/classSoTrackballDragger.html

Cloth UI mapping:
1. The normal avatar editor is for measurements/provider configuration; Pose Mode
   is a dedicated mode for posing.
2. The user selects a bone directly on the mannequin; a collapsed named
   joint list remains available when direct selection is difficult.
3. The selected joint gets a 3D rotation gizmo; direct dragging is the primary input.
4. Symmetry and 5-degree angle snapping are visible mode toggles.
5. The selected joint shows compact X/Y/Z readouts; sliders are intentionally
   removed because they duplicate the gizmo without offering a clearer spatial
   mapping.
6. Exact Euler values remain behind a collapsed Exact angles drawer as a precision
   and accessibility fallback.
7. Presets provide T-pose, Standing, Sewing and Sitting starting points.
8. The joint list is collapsed by default and retained as a recovery/recognition
   path for crowded views or builds without viewport picking.
9. Apply/Rebuild and Cancel preserve the existing staged/persistent document
   semantics.
10. IK and anatomical joint-limit authoring remain explicit follow-up work.

This is intentionally a UI layer over the merged `SkeletonPose`/FK data model;
it does not replace the rig or introduce a second pose representation.

## Direct-manipulation UI audit (2026-10-05)

The current vendor workflows converge on the same interaction hierarchy: select in
the canvas, drag to transform, preview a snap before committing, and expose exact
numeric values only as a secondary precision path.

- Blender's viewport gizmos provide direct move/rotate/scale handles. Snapping can
  be toggled persistently or held temporarily, and modifier keys provide coarse or
  fine control. See:
  https://docs.blender.org/manual/en/latest/editors/3dview/display/gizmo.html
  https://docs.blender.org/manual/en/latest/editors/3dview/controls/snapping.html
- CLO 3D's 2026 Select/Move/Transform workflow uses click-drag for pattern movement,
  Shift/Ctrl-guided constrained movement, drag handles for scale/rotation, and a
  numeric transform dialog as a fallback. See:
  https://support.clo3d.com/hc/en-us/articles/360000012128-Select-Move-Transform-Pattern
  https://support.clo3d.com/hc/en-us/articles/115012381568-Transform-Pattern
- CLO's Arrangement Points show on the avatar; hovering with a selected pattern
  produces a placement preview and clicking confirms the placement. Precise
  placement remains available from the gizmo or property editor. See:
  https://support.clo3d.com/hc/en-us/articles/115001999287-Arrange-Pattern-with-Arrangement-Points-Flip-Wrap-Direction
- CLO sewing uses cursor-following blue guide points and snapping while the user
  click-drags a seam. Numeric seam length entry is available only as an alternate
  path. See:
  https://support.clo3d.com/hc/en-us/articles/360001754628--3D-Tool-Free-Sewing
  https://support.clo3d.com/hc/en-us/articles/360001771047--3D-Tool-Segment-Sewing
- Marvelous Designer follows the same Arrangement Point hover-preview/click-place
  model, reinforcing that snapping is most useful when it is spatially discoverable
  rather than encoded as typed coordinates. See:
  https://support.marvelousdesigner.com/hc/en-us/articles/47358262924185-Arrange-Pattern-with-Arrangement-Points-Flip-Wrap-Direction
- Style3D strengthens the pattern with multi-point snapping, curve-point/handle
  dragging, drag-to-edit sewing endpoints, and automatic arrangement based on
  sewing relationships. This suggests a staged evolution for Cloth: one-point
  snapping first, then attachment/seam guides and multi-point constraints. See:
  https://help.style3d.com/studio/en/1f8f/39dc
  https://help.style3d.com/studio/en/c4905/c2c8/5869/0792/ebff/13f8/12d5
  https://help.style3d.com/studio/en/c4905/d2d78/7ae53/a918/fdca/27f6
- Lectra Modaris 3D emphasizes synchronized edits between 2D production patterns
  and 3D prototypes, so direct 3D manipulation should remain a frontend to the
  same persistent pattern data rather than a separate 3D-only representation. See:
  https://www.lectra.com/en/fashion/products/modaris
- Seamly2D reinforces measurement-driven parametric drafting: dimensions belong to
  the pattern model, while the editing surface stays graphical. See:
  https://wiki.seamly.io/wiki/Main_Page/en
- FreeCAD's Python API exposes 3D-view mouse callbacks and screen/world conversion,
  making a focused interaction controller feasible without introducing a second
  geometry engine. See:
  https://reqrefusion.github.io/FreeCAD-Documentation-html/wiki/en/Code_snippets.html

Implementation mapping for Cloth:
1. Make Arrange/Fit a direct-manipulation stage in the 3D view.
2. Use existing persistent ArrangementPoint visual objects as snap targets.
3. Show snap feedback near the pointer and commit the final placement through the
   existing FittingCommands persistence boundary.
4. Keep the property editor as the precision escape hatch rather than the primary
   placement workflow.
5. Keep solver/material precision controls collapsed behind an explicit expert
   section while retaining the existing quality presets.

This intentionally does not duplicate mannequin joint editing or add an alternate
rig, and it does not change solver contracts.


## Avatar Pose Gizmo refinement (2026-10-08)

## Avatar Pose UI audit and simplification (2026-10-08)

The remaining UI was reviewed against Blender Pose Mode, CLO/Marvelous
Designer avatar posing, FreeCAD task-panel guidance, and general direct-
manipulation principles.

The resulting hierarchy is deliberately viewport-first:

- Select the bone in the 3D view; hover feedback shows what will be selected.
- Drag the native rotation ring to pose; continuous preview keeps the result
  visible before Apply.
- Use Mirror and 5° Snap as compact mode toggles rather than fields or menus.
- Use a named Joint list only when direct selection is difficult.
- Use Exact angles only for precision/accessibility work.
- Reset remains visible because recovery is common and low-risk.
- Apply/Cancel stay at the task-panel boundary; no duplicate custom footer is
  needed.

The choice removes the three always-visible rotation sliders. A slider presents
an abstract value axis, while the gizmo already presents the same three axes in
the spatial context of the selected joint. The two controls therefore compete
for the same task rather than complementing it. This also follows FreeCAD's
task-panel guidance to expose common controls by default and progressively
disclose advanced settings.

Mirror defaults to off so bilateral edits are an explicit action rather than a
surprising side effect. 5° Snap likewise defaults to off; exact-angle entry
bypasses snap so "Exact angles" means literal numeric editing.

Bone hover highlighting is intentionally transient and viewport-local. It improves
recognition without adding another permanent panel control. The joint list remains
the fallback because direct manipulation can become ambiguous in crowded anatomy
and is unavailable in some FreeCAD/SWIG configurations.

The pose viewport should keep the whole authored rig visible in the X-ray overlay,
not only the subset of joints currently exposed as manual controls. Structural bones
remain muted, controllable bones are stronger, and the active joint/bone is
highlighted. This follows the common Pose Mode convention in Blender: the rig stays
visible while selection state communicates what will be transformed.

For 3D rotation, the primary control now prefers FreeCAD's own registered
`SoTransformDragger`. Pose Mode hides its translation and planar-translation
components and exposes the three native rotation axes, preserving FreeCAD's axis
colors and camera-aware autoscaling. This is a better reuse boundary than invoking
the higher-level `Std_TransformManip` command because Cloth is editing staged
joint-rotation data rather than an object's persistent Placement. The existing
Coin
`SoTrackballDragger` remains as a compatibility fallback for FreeCAD builds where
the native runtime type is unavailable.

Bone picking follows the same direct-manipulation convention: clicking the visible body of a
controllable bone selects that joint, with the endpoint/joint hotspot retained as a fallback
for crowded joints. Structural helper bones stay visible for orientation but are not direct pose
targets until the pose data model exposes them as editable controls.

References:
- Blender Pose Mode: https://docs.blender.org/manual/en/latest/animation/armatures/posing/introduction.html
- Blender bone display/selection: https://docs.blender.org/manual/en/latest/animation/armatures/bones/properties/display.html
- FreeCAD native transform dragger: https://github.com/FreeCAD/FreeCAD/blob/main/src/Gui/Inventor/Draggers/SoTransformDragger.h
- FreeCAD transform editing: https://github.com/FreeCAD/FreeCAD/blob/main/src/Gui/ViewProviderDragger.cpp

## Seam highlighting and authoring interaction audit (2026-10-09)

### Evidence from garment tools and Blender

| Tool / documented pattern | Useful observable behavior | Design implication for Cloth |
| --- | --- | --- |
| CLO 2D Segment Sewing | Click one pattern segment, hover the mate, and drag the directional notches before clicking. When sewing length difference is material, the mismatch is surfaced rather than silently accepted. [Official workflow](https://support.clo3d.com/hc/en-us/articles/115012381248-Segment-Sewing) | Put the counterpart and direction feedback in the same interaction; make reversal/mismatch visible before Commit. |
| CLO 3D Segment Sewing and Free Sewing | Sew directly on 3D garment outlines; the same sewing lines appear in 2D and 3D. A blue guide point indicates correspondence and snaps when close; sewable segments are emphasized while the tool is active. [3D Segment Sewing](https://support.clo3d.com/hc/en-us/articles/360001771047--3D-Tool-Segment-Sewing), [3D Free Sewing](https://support.clo3d.com/hc/en-us/articles/360001754628--3D-Tool-Free-Sewing) | Allow edge picking in the viewport, show live pair feedback, retain the preview/commit/cancel boundary, and reuse the canonical seam on every view. |
| CLO sewing visibility and editing | Sewing lines can be hidden when a view becomes crowded; selected lines are bolded and a color chip identifies the selected sewing line. [Edit Sewing](https://support.clo3d.com/hc/en-us/articles/115012380148-Edit-Sewing), [Show/Hide Sewing](https://support.clo3d.com/hc/en-us/articles/115000528428--Popup-Show-Hide-Sewing) | The Seam Overlay Options dialog exposes show/hide and depth-aware occlusion; hover-only labels keep the view uncluttered. Selected-seam isolation remains a possible follow-up. |
| Blender 3D View snapping | Offers edge/face targets, surface projection, optional target-normal alignment, and selectable snapping modes. This is general-purpose geometry interaction, not paired garment sewing. [Blender snapping manual](https://docs.blender.org/manual/en/latest/editors/3dview/controls/snapping.html) | Reuse predictable hover/pick/target feedback. Do not equate Blender UV seam marking with Cloth's semantic relationship between two different PatternPiece edges. |

### Problems found in the previous presentation path

The previous path relied primarily on setting ViewObject.LineColor for persistent Part features. That property remains useful for the tree/document view, but does not itself provide an explicit relationship cue, direction indicator, side-specific identity, or guaranteed refresh tied to the active viewport. A matching RGB is ambiguous when edges overlap and insufficient as the only cue for color-vision differences.

The overlay path now creates a non-persistent Coin3D subtree in the active viewport: each canonical seam draws both sampled edge paths in the SeamId color, direction arrows, a directional notch, and short paired labels with -A/-B suffixes. It follows the canonical semantic reference and is discarded on workbench change; no extra seam identity or persisted visualization object is introduced. Direct edge picking uses FreeCAD's viewport hit information and native selection API, then feeds the existing staged Preview/Commit/Cancel transaction.

### Good-practice checklist

- **Identity before decoration:** SeamId is the authority; deterministic color and short A/B labels derive from it.
- **Redundant encoding:** the color, matching identifier and directional marks all communicate pairing; never rely on RGB alone.
- **In-context preview:** emphasize eligible edges during authoring, identify Side A after the first click, then show both sides and orientation before commit.
- **Reversibility:** keep Preview, Commit and Cancel distinct. Reject a second edge from the same piece before creating document state.
- **Lifecycle and scope:** transient overlays are derived from valid semantic references, refresh after recompute/restore/view entry, and are not serialized as another source of truth.
- **Crowded-view recovery:** expose hide/show and depth-aware occlusion, display labels only for the hovered seam, and retain native edge selection and task-panel status as accessible fallbacks. Selected-seam isolation remains a follow-up.

### Limits

This is a FreeCAD-native workflow informed by documented public behavior, not a claim of CLO/Blender feature parity. The viewport picker is a two-edge shortcut for 1:1 seams; M:N/free relationships use the same direct edge-picking control but still require an explicit Preview. Snapping blue guide points to arc-length correspondence and selected-seam isolation remain candidates for a later bounded change.


## Viewport gizmo visual system audit (2026-10-10)

This pass audits four transient viewport presentations: Pose Mode's skeleton/rotation
control, Interactive Arrange's snap marker, the 3D Pattern Pen stroke, and the semantic
Seam Overlay. Shared style tokens now live in `freecad_cloth/shared/viewport_gizmo_style.py`
for Pose Mode, Interactive Arrange, and Seam Overlay; they are presentation only and do
not define document or solver state. The Surface Pen was reviewed but kept unchanged until
a new closure marker can be checked in real FreeCAD viewport captures.

### Findings and design decisions

| Surface | Audit finding | Change |
| --- | --- | --- |
| Pose rig and rotation gizmo | The XYZ axis convention was already recognizable, but selected rig lines, selected-joint point, and native dragger active color used slightly different amber values. Ring geometry and rig weights were embedded as literals. | Keep conventional XYZ hues; centralize dimensions and line/point weights; use one amber active color for selected bone/joint and dragged ring. Structural bones remain subdued and editable bones remain stronger. |
| Arrangement snap target | The cyan ring/crosshair has a clear meaning, but its palette, dimensions and tessellation were local literals. A low-segment ring can look faceted when zoomed in. | Keep the recognizable cyan snap cue, centralize dimensions, and use a 48-segment ring. The target remains transient and appears only during a live snap preview. |
| 3D Pattern Pen | The orange stroke is intentionally the dominant cue because it represents the user's active tracing input, not a secondary target. Start/closure markers may help but can clutter distant or small strokes. | Keep the existing orange path and sampling semantics unchanged in this pass; point markers need inspection against real FreeCAD mannequin views at multiple zoom levels before changing the closure cue. |
| Semantic seams | Default seam lines were comparatively heavy (3.5) and focused lines heavier still (5.5), which can dominate a crowded garment view. Stable seam identity colors and A/B labels already provide redundant identity. | Reduce ordinary lines to 2.4 and focused lines to 4.0 while retaining thinner correspondence connectors and hover-only labels. Semantic Seam IDs keep their deterministic identity colors. |

### Visual contract

- **Color has a job.** Red/green/blue are axis identity; amber is the active joint/control; cyan is a live snap target; orange is a surface stroke. Semantic seam hues remain identity-specific, and red remains available for invalid/stale geometry rather than ordinary selection.
- **Use more than color.** Pose selection changes line/point weight; the snap marker has a ring, center and crosshair; seam pairs have matching identity colors, A/B labels and directional marks. The pen keeps its existing high-contrast path while a dedicated start marker awaits rendered-view validation.
- **Keep the model first.** Secondary skeleton segments are muted, seam labels appear only on hover, and the snap marker is transient. The Surface Pen remains a deliberate exception: its stroke must be prominent enough to trace on a mannequin. The viewport remains the main work surface rather than turning overlays into a second panel.
- **Keep overlays disposable.** Geometry is regenerated from current data and removed on controller teardown. No gizmo, hover state, active marker or pen sample becomes persistent document data.
- **Keep fallbacks.** Exact-angle pose entry, native selection, task-panel context and non-viewport controls remain available when direct manipulation is difficult or Coin/Pivy is unavailable.
- **Preserve geometry and meaning.** These changes alter only Coin3D presentation. They do not change pose transforms, snapping thresholds, arrangement placements, seam correspondence, mesh topology, pattern extraction tolerances or simulation inputs.

### References checked on 2026-10-10

- FreeCAD Developers Handbook — [Design Guide](https://freecad.github.io/DevelopersHandbook/designguide/) and [Primary Elements / Task Panels](https://freecad.github.io/DevelopersHandbook/designguide/elements.html): recommends restrained viewport overlays, consistent controls, compact default task panels and progressive disclosure.
- FreeCAD Developers Handbook — [UI Zones](https://freecad.github.io/DevelopersHandbook/designguide/zones): reserves the main view for the work and says overlays should be minimal and used sparingly.
- FreeCAD documentation — [Artwork Guidelines](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Artwork_Guidelines.md): a limited palette improves cohesive iconography. Shared viewport roles follow the same principle without assuming icon colors prescribe every 3D overlay.
- Blender Manual — [Viewport Gizmos](https://docs.blender.org/manual/en/latest/editors/3dview/display/gizmo.html): uses RGB axes and exposes gizmo operations separately. Blender's [Gizmo API](https://docs.blender.org/api/4.5/bpy.types.Gizmo.html) distinguishes normal and highlighted colors.
- CLO — [Arrange Pattern with Arrangement Points](https://support.clo3d.com/hc/en-us/articles/115001999287-Arrange-Pattern-with-Arrangement-Points-Flip-Wrap-Direction): shows targets around the avatar, placement feedback and precision alternatives.
- CLO — [3D preferences](https://support.clo3d.com/hc/en-us/articles/360001547168-3D): documents unified versus divided move/rotate gizmos and configurable arrangement-point size.

These references describe observed software behavior and recommendations; the concrete colors and dimensions above are Cloth-specific choices, not claims of exact Blender or CLO parity.


## Avatar onboarding, pose presets, and guided garment journey (2026-10-11)

### Findings from the current UI audit

- Avatar creation/edit/pose commands already exist, but users must discover them under **Cloth Sewing → Fitting & Avatar**. The simulation workflow also needs a first-class entry point so users can begin from the workbench where they expect to fit and drape a garment.
- The built-in MakeHuman provider is a posed, landmark-aware human target. The **FreeCAD geometry** provider accepts selected imported geometry as a surface but does not import a source rig, skin weights, or motion data. The UI and onboarding must make this difference explicit instead of implying arbitrary OBJ/FBX files become rigged characters.
- Pose Mode currently offers Standing, Sewing, and Sitting. A near-horizontal **T-pose** is also valuable for assessing shoulder span and garment placement; the current model represents that posture with approximately 12° arm settings in its mannequin convention.
- A tunic is the strongest beginner narrative because it exercises pattern authoring, semantic seams, fitting anchors, pose, material/quality choices, simulation and diagnosis. The blanket remains a separate, lower-complexity test for collision and pinning issues.
- Animation evidence needs accurate labeling. The existing README GIFs are produced by several task-specific acceptance fixtures; they are not yet a single continuous run in one saved tunic document. Fitting-anchor and interactive-arrange clips use tunic panels, while the sewing and pose clips isolate their respective UI flows. Keep that limitation explicit until a single-document GUI journey fixture exists.

### CLO and Blender interaction patterns

| Reference | Observed pattern | Design implication for Cloth |
| --- | --- | --- |
| [CLO: Avatar Open/Add/Save](https://support.clo3d.com/hc/en-us/articles/115002687268-Avatar-AVT-Open-Add-Save) | A visible File → Open/Add → Avatar path, with a format and load-type choice rather than a hidden provider property. | Expose avatar create/edit/pose actions in the workbench used for fitting; state exactly what the provider can consume. |
| [CLO: OBJ import](https://support.clo3d.com/hc/en-us/articles/115000494107-3D-File-OBJ-Import-Export) | OBJ import explicitly distinguishes loading as an avatar, trim, or garment. The help warns that arrangement points are properly generated for A/T-posed avatars and that imported unrigged OBJs cannot be posed like native rigged avatars. | Name the imported-geometry path as geometry-only and avoid promising skeleton/pose import; prefer a T-pose baseline for fitting inspection. |
| [CLO: Pose Open/Save](https://support.clo3d.com/hc/en-us/articles/115002687328-Pose-POS-HPOS-Open-Save) | Named pose library plus explicit pose-only versus pose-and-joint-translation semantics. | Use clearly named, task-oriented presets and keep the distinction between a pose preset and body-size/provider settings. Saving/loading arbitrary user pose assets remains future work. |
| [Blender: Pose Library](https://docs.blender.org/manual/en/5.0/animation/armatures/posing/editing/pose_library.html) | Pose assets are named reusable actions, can have preview images, and are organized through the Asset Browser. | Design the presets as an expandable library concept; a compact row of familiar named actions is a useful first step before a full asset browser. |
| [Blender: Asset Browser](https://docs.blender.org/manual/en/5.0/editors/asset_browser.html) and [Workspaces](https://docs.blender.org/manual/en/5.0/interface/window_system/workspaces.html) | Assets are discoverable in an explicit browser, while workspaces group common task-specific tools and layouts. | Keep Cloth’s workbenches purpose-specific and reduce entry-point hunting by exposing a small Avatar & Fitting group in Cloth Simulation. Do not replicate Blender’s full asset infrastructure in this bounded change. |

### Implemented UX decisions

1. Register **Create Avatar**, **Edit Avatar**, and **Pose Avatar** under **Cloth Simulation → Avatar & Fitting**, while retaining the legacy Cloth Sewing entry points.
2. Add the T-pose to the data model, the editable avatar preset enumeration, and the viewport-first Pose Mode button row. Keep Standing, Sewing and Sitting unchanged for existing users.
3. Update the user guide with the exact standard UI path: built-in MakeHuman creation, then—when appropriate—FreeCAD File → Import, selecting the imported object, choosing FreeCAD geometry, using the selected object and applying/rebuilding. Explain that this does not transfer a skeleton or animation.
4. Make the tunic the recommended human-scale learning journey and preserve the blanket as a deliberate diagnostic case.
5. Be explicit that today’s task GIFs are not yet one continuous interaction recording. A future integrated capture should begin with a new document and carry one persistent tunic through Sketcher-backed pattern creation, seam preview/commit, fitting/arrangement, preset/joint posing, simulation settings, run, diagnosis and save/reload. It should assert the same document/PatternPiece/Seam IDs across stages, and the canonical workflow must regenerate its evidence rather than hand-edit GIFs.

### Visual and interaction principles

- **One obvious first action:** make avatar creation visible where the garment will be fitted.
- **Distinct provider semantics:** a rigged mannequin and a generic imported surface must not look interchangeable in copy or status labels.
- **Recognizable starting poses:** use succinct labeled preset buttons; reserve the viewport for direct joint manipulation and precision values for the collapsed fallback.
- **One garment story:** teach the tunic from first editable pattern to final diagnosis; keep clips useful as local references but do not describe unrelated fixtures as a continuous session.
- **Recovery over decoration:** Apply/Rebuild, Cancel, reset and stale-target guidance matter more than adding controls that do not carry persistent document meaning.
