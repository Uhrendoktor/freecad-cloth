# Cloth workbench icon design

The three workbench icons use the same 64px, single-stroke visual language so they remain legible in FreeCAD's compact workbench selector and dark/light themes.

- **Pattern:** pattern sheet with construction lines and a drafting mark.
- **Sewing:** two facing seam paths with a dashed stitch/crossing cue.
- **Simulation:** draped cloth over a simplified human target.

SVGs use `currentColor` rather than a hard-coded dark color. FreeCAD can therefore render the same assets correctly against light and dark UI themes. Shapes avoid text and fine detail, keep the primary silhouette inside the central 52px area, and use rounded line caps/joins.
