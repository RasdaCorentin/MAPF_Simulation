# diagrammes/ — how to change a diagram

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants — lives in the root [`AGENT.md`](../AGENT.md), which already states that the
> class diagram arbitrates when code and diagram disagree. This file is the process rule that
> makes that binding in practice, not just on paper.

## The rule

**Diagrams are the source of truth, not a record kept after the fact.** Concretely:

1. A code change that adds, removes or reshapes a class, a relation, or a package boundary
   must be mirrored in **every diagram it touches** — not just the one that happens to be open.
   A single seam can appear in several files at once (e.g. a new `Coordinator` subclass belongs
   in `Class_Diagram/class_diag_commented.puml`, in `component_diagram.puml` if it changes a
   package-level seam, and in `Class_Diagram/class_diag_simplified.puml` if it's part of that
   smaller set).
2. **The diagram change must be validated by the user before any of the corresponding code is
   implemented.** Propose the diagram edit first, get it confirmed, and only then write the
   code that makes it true. Reconciling the diagram afterwards — "I'll update it once the code
   is done" — is exactly the failure mode this rule exists to prevent: the diagram silently
   stops being trustworthy the moment it can lag behind.
3. When a change is purely internal to one class (a private method, an implementation detail
   never shown on any diagram), no diagram update is owed — the rule is about what the diagrams
   *claim*, not about the whole codebase.

## Where each diagram lives, and how to regenerate it

| Source | Scope | Regenerate with |
|---|---|---|
| `Class_Diagram/class_diag_commented.puml` | the architecture, annotated: `core` | `plantuml diagrammes/Class_Diagram/class_diag_commented.puml` |
| `component_diagram.puml` | packages and the seams between them | `plantuml diagrammes/component_diagram.puml` |
| `Class_Diagram/class_diag_simplified.puml` | the easiest-to-read rendering — plain attributes, no notes | `plantuml diagrammes/Class_Diagram/class_diag_simplified.puml` |
| `Class_Diagram/Pibt/class_diag_commented.puml` | the `pibt/` package: `PIBTPlanner`, `ReservationTable`, `PriorityManager`, `pibt_core`, `OneShotGoalDispatcher` | `plantuml diagrammes/Class_Diagram/Pibt/class_diag_commented.puml` |
| `Class_Diagram/Export/class_diag_commented.puml` | the `export/` package: `CsvExporter` — the `Exporter` seam itself lives in `Class_Diagram/class_diag_commented.puml`, alongside `PathPlanner`/`MissionOrchestrator` | `plantuml diagrammes/Class_Diagram/Export/class_diag_commented.puml` |

Never edit a generated PNG. `script_perso.sh` watches a `.puml`/`.iuml` file and regenerates it
on save, for iterating live.

There is currently no `Object_Diagram/` — both object diagrams modeled a concrete tick
(`PIBTCoordinator`, `ReservationTable`, `PriorityManager`, `EasiestAllocator`), and the `algo/`
removal (see `TODO.md`) left nothing to instantiate. Deleted outright rather than kept stale,
same as `report_diagram.puml` when `report/` went: a diagram that can no longer be true is not
a record worth keeping under this file's own rule. Reinstate one once a concrete `Coordinator`
exists again to model a real tick against.
