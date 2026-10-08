# Agent observation bundles

## Purpose

The optional observation bundle gives an assistant or reviewer a small, stable entry point into evidence already produced by a FreeCAD batch run. It is created after the FreeCAD process exits and before the existing artifact upload. It does not query a live process, restart FreeCAD, copy evidence, create a second artifact, or add another workflow.

The opt-in feature adds one small JSON manifest to the existing artifact. The selected source files must already be under the artifact path being uploaded. Their bytes are hashed in place; images and geometry files are not duplicated. Normal runs pay no bundle-generation cost while the action input is empty.

## Schema version 1

The manifest file is named agent-observation.json by convention and uses these top-level fields:

- schema and schema_version: stable schema identifier and integer version.
- created_at_utc: ISO-8601 UTC timestamp.
- label: optional short scenario or hypothesis.
- context: repository, exact commit SHA, workflow/job/event, run ID/attempt/URL and pull-request number where available.
- execution: runner OS/architecture, Python version/platform, container image, test script and simulation backend where available.
- evidence: ordered entries with role, path relative to the manifest directory, media type, byte size and SHA-256 of the exact file.

Paths are explicit, relative, and case-sensitive. A reader can verify SHA-256 after extraction. Treat the indexed files—not the manifest—as the diagnostic evidence itself.

Allowed roles and file types:

- summary: JSON, Markdown, plain text or YAML summaries.
- metrics: JSON or CSV measurements.
- geometry: JSON/CSV geometry measurements or STL, OBJ, STEP/STP and BREP geometry exports.
- visual: PNG, JPEG, WebP or SVG viewport evidence.
- model: FreeCAD FCStd, STL, OBJ, STEP/STP or BREP model snapshots.
- config: JSON, TOML, YAML or plain-text configuration.

Logs, archives, caches, arbitrary source files and directory globs are excluded. At most 24 files are allowed; no file may exceed 4,000,000 bytes, and selected evidence totals may not exceed 5,000,000 bytes. The manifest itself is small. These limits bound hashing work and help preserve the repository's 10 MB total workflow artifact budget.

## Enabling an export

Add these optional inputs to an existing freecad-test action call that already uploads the selected evidence:

    artifact-name: pbd-contact-diagnostics
    artifact-path: artifacts/pbd-contact-diagnostics/**
    observation-root: artifacts/pbd-contact-diagnostics
    observation-output: artifacts/pbd-contact-diagnostics/agent-observation.json
    observation-label: PBD contact controls and collision ladders
    observation-files: |
      summary=manifest.json
      metrics=cube-ladder-manifest.json
      metrics=avatar-ladder-manifest.json
      visual=cube-ladder/rung-1-cube-pinned/step-000.png
      visual=cube-ladder/rung-1-cube-pinned/step-090.png
      visual=avatar-ladder/rung-6-avatar-pinned/step-000.png
      visual=avatar-ladder/rung-6-avatar-pinned/step-090.png

Paths after the equals sign are relative to observation-root. Every selected file must exist at export time and must already be included by artifact-path; the action does not silently add or copy evidence. The manifest itself is added to the same upload. An artifact name is required. Missing, unsafe, symbolic-link, duplicate, unsupported or oversized evidence fails closed with a compact error message.

Use stable evidence rather than logs: a concise summary, named metrics with units, before/after viewport images, and only the geometry snapshots needed to disambiguate a failure. Screenshots must come from the exact run and must not be edited. Avoid secrets, user data, unrestricted document dumps and whole logs.

## Geometry conventions

The index schema is stable across tasks; the payload schemas belong to the diagnostics that produce them and should be documented alongside those scripts. JSON geometry and metrics should prefer:

- semantic object/case IDs rather than transient UI labels alone;
- FreeCAD world coordinates in millimetres for lengths and points;
- angles in degrees and elapsed time in seconds;
- bounds, centroid, vertex/face counts, and relevant constraints or anchors;
- numeric measurements with units, explicit checkpoint order and source revision;
- measured values separated from thresholds and PASS/FAIL decisions.

This keeps machine-readable observations separate from rendered evidence. An assistant can inspect the manifest first, verify run provenance, open a small set of views, and then retrieve additional files already included in the same artifact.
