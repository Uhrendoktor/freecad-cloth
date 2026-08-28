# Sewing construction semantics

The pattern layer owns stable piece/edge IDs, seam ranges and construction marks. The solver owns numerical constraint realization.

A plain seam pairs two edge ranges with orientation. If lengths differ slightly, correspondence is parameterized over normalized edge ranges and validation reports the mismatch rather than silently stretching the pattern. Notches are matching marks attached to stable edge IDs and normalized positions.

Mirrored pieces retain distinct IDs; mirroring is a geometric transform, not an identity alias. Sewing order is an optional runtime optimization: the semantic graph describes the final intended connections and the solver may solve constraints simultaneously.

Initially supported construction kinds are plain seam, with reserved semantics for darts, gathers, pleats, hems, folds and closures. Impossible graphs—unknown pieces/edges, duplicate seam IDs, self-seams, or unsupported kinds—are rejected before solver execution.
