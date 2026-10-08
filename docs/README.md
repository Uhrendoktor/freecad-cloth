# FreeCAD Cloth documentation

Use this page as the documentation map. Choose the task you are trying to accomplish rather than starting with repository internals.

## I want to use FreeCAD Cloth

| Goal | Start here | What you get |
| --- | --- | --- |
| Install it | [Installation](INSTALLATION.md) | Requirements, installation and first-run checks |
| Get a first successful simulation | [Examples](EXAMPLES.md) | Small Blanket over Cube tutorial before the full garment |
| Learn the normal garment workflow | [User guide](USER_GUIDE.md) | Pattern → Sewing → Fitting → Pose → Simulation → Diagnosis |
| Learn feature behavior | [Visual wiki](wiki/README.md) | Feature pages with screenshots, persistent state, failure cases and evidence |
| Solve a problem | [Troubleshooting](TROUBLESHOOTING.md) | Symptom → likely cause → recovery path |
| Look up workbench behavior | [Workbench guide](WORKBENCH_GUIDE.md) | Commands, workflow details and document structure |

## I want to understand or change the project

| Goal | Start here | What you get |
| --- | --- | --- |
| Understand the architecture | [Architecture](ARCHITECTURE.md) | Authorities, boundaries, lifecycle and dependency direction |
| Find code ownership | [Project structure](PROJECT_STRUCTURE.md) | Package boundaries and canonical module locations |
| Change the project safely | [Development](DEVELOPMENT.md) | Tests, CI, GUI validation and contribution rules |
| Understand durable design choices | [Decisions](DECISIONS.md) | Architectural decisions and rationale |
| Check release/evidence rules | [Release gates](RELEASE_GATES.md) | Acceptance and visual-evidence requirements |
| Inspect planned capabilities | [Roadmap](ROADMAP.md) | Durable future work, not current status |
| Read design research | [Research](RESEARCH.md) | Design rationale and external references |

## Reading order for a new user

1. [Installation](INSTALLATION.md)
2. [Blanket over Cube](EXAMPLES.md#1-blanket-over-cube)
3. [User guide](USER_GUIDE.md)
4. The relevant [visual wiki](wiki/README.md) page
5. [Troubleshooting](TROUBLESHOOTING.md) when something behaves unexpectedly

Start with the blanket when diagnosing an installation, target or simulation problem. It removes most garment-specific variables before you move to the tunic.

## Documentation authority

Each kind of information has one intended home:

| Information | Canonical home |
| --- | --- |
| Project orientation | root [README](../README.md) |
| User-facing feature behavior | [wiki/](wiki/README.md) |
| Step-by-step workflows | [USER_GUIDE.md](USER_GUIDE.md) and [WORKBENCH_GUIDE.md](WORKBENCH_GUIDE.md) |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Code/package ownership | [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) |
| Durable decisions | [DECISIONS.md](DECISIONS.md) |
| Testing/CI/contributor workflow | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Current coordination state | `AGENT_STATUS.md` / `TOOL_STATE.md` |
| Task-local evidence | GitHub issue/PR and its exact CI artifacts |
| Research | [RESEARCH.md](RESEARCH.md) |

Current coordination files are snapshots, not architectural authorities. Verify implementation claims against the current branch and HEAD before treating a status statement as current fact.

Generated images are evidence artifacts. The current source, executable tests and canonical workflow remain authoritative.
