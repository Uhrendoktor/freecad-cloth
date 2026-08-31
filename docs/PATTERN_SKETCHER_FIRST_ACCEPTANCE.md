# Pattern Sketcher-first acceptance

Release acceptance for the native Sketcher-first Pattern authoring slice.

## Public workflow

1. Activate the **Cloth Pattern** workbench.
2. Create a new Pattern Piece through the public command/task panel.
3. Confirm the Pattern Piece owns/links a native `Sketcher::SketchObject` and that Sketcher is the authoritative geometry representation.
4. Select the piece and use **Edit Sketch** to enter the native Sketcher editor.
5. Add or edit native Sketcher geometry/constraints without invoking the legacy polygon drafting editor.
6. Recompute and verify the Pattern Piece remains valid and its semantic identity is preserved.
7. Save, close and reload the document; verify the Sketch link and semantic Pattern Piece properties survive.
8. Create a second piece and verify normal Sewing commands can consume the resulting Pattern Pieces.

## Regression requirements

- Default piece creation must attach a native Sketcher object.
- The public edit action must enter that Sketcher object directly.
- The legacy sketch-generation command remains available only for compatibility/migration.
- No second constraint solver or duplicate drafting kernel is introduced.
- Semantic Cloth metadata remains outside Sketcher while Sketcher owns geometry.
- `GeometryAuthority=Sketcher` is the persistent authority marker; the legacy `GeometryMode` remains limited to its existing `Rectangle`/`Custom` values.

## CI gate

This checklist is documentation only; the canonical workflow remains the sole CI workflow and is responsible for the real FreeCAD/Xvfb acceptance evidence.
