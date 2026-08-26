# AGENT.md

> **This is the project map for coding agents. Start here, then read the guide for the package
> you are about to touch. Do not re-explore the tree to answer structural questions.**

**Two companion files are binding and are *not* reproduced here:**
- **`CONVENTION.md`** — repository layout, branch naming, and Conventional Commits. Every commit,
  file name and new file must follow it. Read it before your first commit.
- **`README.md` / `GUIDE.md`** — human-facing overview and guided tour.

The reference for architecture is the class diagram: when this file, the code and the diagram
disagree, **the diagram arbitrates** — see *Rules and invariants*. It is imported below so it is
always in context; read it, do not re-derive it.

@diagrammes/Class_Diagram/class_diag_commented.puml

---

## Package guides — where the class-by-class detail lives

This file holds only what is **cross-cutting**: how to run the thing, the layout, the dependency
direction, the rules and the invariants. Everything about a specific class lives next to it.

| Guide | Covers |
|---|---|
| [`core/AGENT.md`](core/AGENT.md) | `Coordinates2D`, `WorldEntity`, `Orientation`, `Agent`, `Objective`, `Grid2D`, `StepOutcome`, `AssignmentManifest`, `PathPlanner`, `MissionOrchestrator`, `Exporter`, `WorldEngine` — and the tick |
| [`pibt/AGENT.md`](pibt/AGENT.md) | `PIBTPlanner`, a concrete `PathPlanner` (Priority Inheritance with Backtracking) |
| [`export/AGENT.md`](export/AGENT.md) | `TraceCsvExporter`/`AggregateCsvExporter`/`CompositeExporter`, concrete `Exporter`s (log a run's trace and/or its summary to `log/*.csv`) |
| [`diagrammes/AGENT.md`](diagrammes/AGENT.md) | the binding rule for changing a diagram — read it before touching one |

**Working on one package?** Root + that guide is enough.

`client/`, `report/`, `algo/` and `mrta/` are all gone as of this and earlier refactors — see
`TODO.md` for exactly what that broke and why it was left broken rather than patched. `pibt/` and
`export/` are `core/`'s two dependents right now — `pibt/` restores one concrete `PathPlanner`
from what `algo/` used to provide, `export/` supplies a concrete `Exporter`; neither depends on
the other. See [`pibt/AGENT.md`](pibt/AGENT.md) and [`export/AGENT.md`](export/AGENT.md).

---

## Running the simulation

`main.py` is still broken (depended on `client.control`/`report`), and so are `sim_many_pibt.py`,
`sim_many_lacam.py` and `sim_many_pibt_plus.py` (imported a concrete `PathPlanner` from `algo/`
by name) — all four raise `ImportError` at the top-level import, see `TODO.md`.
`pibt/demo_one_shot.py` is the first thing in the repo that runs a full tick end to end again:
`python -m pibt.demo_one_shot` wires a `Grid2D`, a few `Agent`s, `PIBTPlanner` and `pibt`'s own
`OneShotGoalDispatcher` (one-shot fixed goals, not `mrta` — gone, and `core` dropped its own
`FixedGoalDispatcher` too, see `core/AGENT.md`) and steps the engine to convergence.

A run can be logged to CSV by attaching an `export.Exporter` to the `WorldEngine` instead of just
stepping it — `demo_trace_log.py` writes a per-tick trace under `log/trace/`, `demo_aggregate_log.py`
runs the scenario three times through `CompositeExporter` and appends three rows to
`log/aggregate.csv`; see `export/AGENT.md`. `pibt/demo_one_shot.py` itself does not do this yet.

There is currently **no test suite either**, and no working de-facto regression check beyond that
one demo script. `core/`, `pibt/` and `export/` all still import cleanly and their internals can
be exercised directly (construct a `Grid2D`/`Agent` by hand, no scenario wiring needed).

---

## Layout

```
.
├── core/          — pure engine, zero rendering dependency        -> core/AGENT.md
│   ├── entities/  — position.py, entity.py, orientation.py, agent.py, objective.py
│   ├── environment/ — grid.py (spatial source of truth)
│   └── engine/    — plan_result, dispatch_intent, coordinator, dispatcher, simulation
│
├── pibt/          — Priority Inheritance with Backtracking, depends only on core -> pibt/AGENT.md
│                    reservation_table, priority_manager, pibt_core, pibt_planner, demo_one_shot
│
├── export/        — concrete Exporters, depends only on core                   -> export/AGENT.md
│                    trace_csv_exporter, aggregate_csv_exporter, composite_exporter
│
├── diagrammes/    — PlantUML sources + PNGs; script_perso.sh watches and regenerates -> diagrammes/AGENT.md
├── main.py               — BROKEN: imported client.control/report, both removed — see TODO.md
├── sim_many_pibt.py      — BROKEN: imported a concrete PathPlanner from algo/, removed — see TODO.md
├── sim_many_lacam.py     — BROKEN: same reason — see TODO.md
├── sim_many_pibt_plus.py — BROKEN: same reason — see TODO.md
├── TODO.md · README.md · GUIDE.md · CONVENTION.md · CLAUDE.md
└── requirements.txt · LICENSE
```

`core/` carries an `__init__.py` re-exporting its public names; `core/AGENT.md` lists them.
`experiments.csv` and `sim_results.csv` may sit at the root — gitignored outputs.

**Dependency direction:** `core/` has no outgoing dependencies — a pure engine, no rendering or
allocation coupling. `pibt/` and `export/` are its two dependents right now, neither depending on
the other:

```
pibt   -> core
export -> core
```

`pibt/PIBTPlanner` is a concrete `PathPlanner` and `export/TraceCsvExporter` (among others) a
concrete `Exporter`; there is still nothing implementing `MissionOrchestrator` in `core/` itself (see
`pibt/one_shot_dispatcher.py` for a local, package-scoped one) — see `TODO.md`.

---

## Rules and invariants

Two different things, kept apart on purpose. A **rule** constrains what you may write — breaking
one is a layering bug, and no amount of local convenience justifies it. An **invariant** is a
property the code already guarantees; your change does not have to restate it, but it must not
break it. When in doubt, the class diagram arbitrates.

### Hard rules — never violate these

- **`core/` must never import anything above it.** It is a pure engine with zero rendering or
  allocation coupling — nothing in the repository currently sits above it, and that must stay a
  one-directional dependency whenever something does again.
- **The class diagram is the reference.** When code and `class_diag_commented.puml` disagree, the
  default is to change the *code* so the diagram becomes true; amend the diagram only when it is
  genuinely wrong. The component and object diagrams follow the class diagram, never the reverse.
- **Diamonds follow one rule** (stated at the top of `class_diag_commented.puml`): filled for an
  immutable value or a mutable object with a single exclusive owner, hollow for a shared mutable
  instance.
- **Every diagram change is validated before the code that makes it true is written.** See
  [`diagrammes/AGENT.md`](diagrammes/AGENT.md) for the full rule.
- **Keep the diagrams in sync.** Three sources, each with its own scope:

  | Source | Scope | Regenerate with |
  |---|---|---|
  | `diagrammes/Class_Diagram/class_diag_commented.puml` | the architecture, annotated: `core` | `plantuml diagrammes/Class_Diagram/class_diag_commented.puml` |
  | `diagrammes/component_diagram.puml` | packages and the seams between them | `plantuml diagrammes/component_diagram.puml` |
  | `diagrammes/Class_Diagram/class_diag_simplified.puml` | the easiest-to-read rendering | `plantuml diagrammes/Class_Diagram/class_diag_simplified.puml` |
  | `diagrammes/Class_Diagram/Pibt/class_diag_commented.puml` | the `pibt/` package | `plantuml diagrammes/Class_Diagram/Pibt/class_diag_commented.puml` |
  | `diagrammes/Class_Diagram/Export/class_diag_commented.puml` | the `export/` package | `plantuml diagrammes/Class_Diagram/Export/class_diag_commented.puml` |

  Never edit the generated PNGs. There is no sequence diagram: `sequence_tick.puml` was dropped —
  the tick order it showed is stated on `WorldEngine` in the class diagram and in
  [`core/AGENT.md`](core/AGENT.md). There is currently no `Object_Diagram/` either — both
  modeled a concrete tick through classes that no longer exist; see `diagrammes/AGENT.md`.

### Invariants — properties the code already maintains

| Constraint | Detail |
|---|---|
| One agent per cell | `Grid2D.place()` raises; `WorldEngine.advance_time_step()` lifts all movers before placing them |
| `Coordinates2D` is immutable | frozen dataclass, never mutated |
| `Agent` is hashable | via `agent_id`, usable as a dict key |
| Deferred spawn | `appear_at > 0` -> held in `_pending` until the right step |
| PathPlanner is mandatory | `WorldEngine` refuses to run without one; a mission orchestrator is optional |
| Obstacle = WorldEntity | `WorldEntity(id, pos, blocks_movement=True)` suffices — no subclass |
| `StepOutcome` is the universal contract | every `PathPlanner.plan()` returns one; diagnostics are optional |
| `AssignmentManifest` decouples allocation from navigation | goals/priorities flow only through the manifest; no external mutation of the planner, so any PathPlanner pairs with any MissionOrchestrator |
| Single mover | only `WorldEngine.advance_time_step()` moves agents (lift→`move_to`→place); `agent.move_to` alone must not be called |
| Plans are validated, not rolled back | `WorldEngine._validate_plan()` rejects an inapplicable `StepOutcome` **before** any mutation, so the lift/place transaction cannot fail partially |

A few invariants used to live here that named `algo/` or `mrta/` classes directly (PIBT's
goal-stability rule and `-inf` demotion policy, the two allocators' seeded-RNG guarantee, mission
identity belonging to the registry that stamped `task_id` at intake, the intake guard + progress
watchdog that kept an unreachable mission from consuming an agent forever) — dropped along with
`algo/` and `mrta/` themselves rather than kept as a promise nothing currently makes. Whatever
implements `PathPlanner`/`MissionOrchestrator` next should restate the ones that still apply.

No invariant currently describes a multi-cell entity: `Zone` filled that role and was removed
once nothing depended on it — see [`core/AGENT.md`](core/AGENT.md).
