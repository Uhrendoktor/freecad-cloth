# SVG interchange decision

SVG is the first interchange format because it is ubiquitous, unit-aware, text-based, easy to validate in CI, and does not require a native CAD dependency. DXF remains a future adapter because its entity semantics and library licensing/build combinations need a separate audit.

`PatternExport.to_svg()` emits 1:1 dimensions, `width`/`height` with the selected units, a numeric `viewBox`, and a `data-units` attribute. The sewing boundary is kept as a distinct path and stable segment IDs are preserved in `data-edge-ids`. This is intentionally structural SVG rather than a claim of full DXF/SVG semantic parity.

Known limitation: curves are sampled to a polyline for interchange. A future exporter may emit native SVG path curves when the source geometry exposes them directly. Import is deferred until a stable schema for mapping SVG groups back to sewing/cut boundaries is established.

The implementation uses only Python's standard library and introduces no GPL-incompatible dependency.
