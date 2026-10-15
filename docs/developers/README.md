# FreeCAD Cloth developer documentation

This section is for people changing, testing, reviewing, or maintaining the software.

## Start with

| Goal | Guide |
| --- | --- |
| Set up the development and validation environment | [Development guide](DEVELOPMENT.md) |
| Understand authority, dependencies, and package boundaries | [Architecture](ARCHITECTURE.md) |
| Find module ownership and the repository layout | [Project structure](PROJECT_STRUCTURE.md) |
| Review durable engineering decisions | [Architecture decisions](DECISIONS.md) |
| Maintain user-facing documentation | [Documentation guide](DOCUMENTATION_GUIDE.md) |
| Validate numeric and data-boundary contracts | [Math validation](MATH_VALIDATION.md) |
| Review release readiness | [Release gates](RELEASE_GATES.md) |

## Further references

- [Backend evaluation](BACKEND_EVALUATION.md), [library evaluation](LIBRARY_EVALUATION.md), and [research notes](RESEARCH.md) describe technical choices and investigation.
- [Roadmap](ROADMAP.md), [feature matrix](FEATURE_MATRIX.md), and [benchmark-driven improvements](BENCHMARK_DRIVEN_IMPROVEMENTS.md) record planning or historical analysis; they are not live repository status.
- [CI configuration](CI_CONFIGURATION.md), [simulation review](SIMULATION_REVIEW.md), [visual validation](VALIDATION.md), and [scene understanding](SCENE_UNDERSTANDING_FOR_CLOTH.md) describe testing and review.
- [UI style guide](UI_STYLE_GUIDE.md) covers interaction and presentation conventions.

The [FreeCAD user documentation](../users/README.md) is maintained separately. AI-specific guidance belongs in [Agent documentation](../agents/README.md); repository-wide agent instructions remain in the root [`AGENTS.md`](../../AGENTS.md).
