# FreeCAD Cloth documentation

This is the repository's human-facing, wiki-ready documentation hub. Versioned `docs/` content is the canonical source of truth; its navigation is intentionally structured so the same pages can be mirrored into GitHub Wiki without creating a second documentation hierarchy.

For a new user, use this path:

1. **[Installation](INSTALLATION.md)** — supported runtime, installation, first-run verification, and developer/CI notes.
2. **[User guide](USER_GUIDE.md)** — the shortest Pattern → Sewing → Arrange/Fit → Simulate journey, recovery, and diagnostics.
3. **[Examples](EXAMPLES.md)** — the validated Blanket over Cube smoke test and the advanced tunic path.
4. **[Workbench guide](WORKBENCH_GUIDE.md)** — command-level details and the document/data model behind the UI.
5. **[Release gates](RELEASE_GATES.md)** — what is actually implemented and validated, and what remains roadmap work.

The remaining technical references are intentionally separate:

- **[Architecture](ARCHITECTURE.md)** — authoritative data ownership, dependency direction, invalidation, and persistence contracts.
- **[Project structure](PROJECT_STRUCTURE.md)** — canonical package/module layout.
- **[Research](RESEARCH.md)** — garment-workflow research and FreeCAD mapping; research is not a feature promise.
- **[Development](DEVELOPMENT.md)** — testing, CI, screenshots, and contribution/agent guidance.
- **[Roadmap](../ROADMAP.md)** — planned capability beyond the currently validated product boundary.

## Wiki-ready information architecture

If the same content is later mirrored into GitHub Wiki pages, keep this navigation and source-of-truth split:

| Human-facing page | Repository source |
|---|---|
| Home / Getting Started | `README.md` + `docs/README.md` |
| Installation | `docs/INSTALLATION.md` |
| User Guide | `docs/USER_GUIDE.md` |
| Examples | `docs/EXAMPLES.md` |
| Workbench Guide | `docs/WORKBENCH_GUIDE.md` |
| Troubleshooting | `docs/USER_GUIDE.md#troubleshooting-and-diagnostics` |
| Technical Reference | `docs/ARCHITECTURE.md` + `docs/PROJECT_STRUCTURE.md` |
| Release / capability boundary | `docs/RELEASE_GATES.md` + `ROADMAP.md` |

Do not create a second, competing copy of these procedures without a concrete reason. Versioned `docs/` is the source of truth for behavior that must match a particular repository revision.

## Workbench model

```text
Cloth Pattern → Cloth Sewing → Cloth Simulation
       │              │              │
       └──── semantic document model ────┘
                         │
                    solver-neutral
                     derived state
```

FreeCAD remains the geometry and document-persistence authority. Cloth owns garment semantics such as PatternPieces and seams. Simulation owns derived mesh, collision, and solver state.

## Authoritative technical references

- [FreeCAD documentation](https://wiki.freecad.org/) — host application, workbench, Sketcher, Python-console, and package guidance.
- [FreeCAD documentation source](https://github.com/FreeCAD/FreeCAD-documentation) — versioned source for the official documentation.
- [Python 3.12 documentation](https://docs.python.org/3.12/) — runtime/library reference for the supported Python baseline.
- [FreeCAD Cloth repository](https://github.com/Uhrendoktor/freecad-cloth) — implementation, tests, releases, and issue history.

External documentation can change independently of this repository; use the current vendor documentation for host-application details. The repository-specific commands and capability boundary are defined by `main` and the documents linked above.

## Visual evidence

The README and example pages refer only to stable assets published by the canonical workflow on the `docs/screenshots` branch. They are derived evidence, not hand-edited screenshots:

- Blanket motion: `cloth-blanket-motion.gif`
- Tunic final view: `cloth-simulation-draped-front.png`
- Arranged simulation turntable: `cloth-simulation-arranged-turntable.gif`
- Draped simulation turntable: `cloth-simulation-draped-turntable.gif`
- Avatar turntable: `cloth-avatar-turntable.gif`

The repository's visual acceptance policy is documented in [Release gates](RELEASE_GATES.md).
