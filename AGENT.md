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
| [`core/AGENT.md`](core/AGENT.md) | `Coordinates2D`, `WorldEntity`, `Orientation`, `Agent`, `Objective`, `Grid2D`, `StepOutcome`, `AssignmentManifest`, `PathPlanner`, `MissionOrchestrator`, `WorldEngine` — and the tick |
| [`mrta/AGENT.md`](mrta/AGENT.md) | `Mission` lifecycle, mission sources, `TaskDrivenOrchestrator`, eligibility, the watchdog, domain vocabulary |
| [`diagrammes/AGENT.md`](diagrammes/AGENT.md) | the binding rule for changing a diagram — read it before touching one |

**Working on one package?** Root + that guide is enough. Changing a *seam* between two — an ABC,
a DTO, an import direction — read both guides and the rules below.

`client/`, `report/` and `algo/` are all gone as of this and an earlier refactor — see `TODO.md`
for exactly what that broke and why it was left broken rather than patched.

---

## Running the simulation

Nothing runs end to end right now. `main.py` and `sim_many_mrta.py` were broken first (depended
on `client.control`/`report`); `sim_many_pibt.py`, `sim_many_lacam.py` and `sim_many_pibt_plus.py`
were broken after (depended on a concrete `PathPlanner` from `algo/`). All five raise
`ImportError` at the top-level import — see `TODO.md` for the full picture and what unblocking
any of them actually needs.

There is currently **no test suite either**, and no working de-facto regression check to fall
back on. `core/` and `mrta/` still import cleanly and their own internals can be exercised
directly (construct a `Grid2D`/`Agent`/`Mission` by hand, no scenario wiring needed) — there is
just nothing that runs a full tick without a `PathPlanner` implementation to plug in.

---

## Layout

```
.
├── core/          — pure engine, zero rendering dependency        -> core/AGENT.md
│   ├── entities/  — position.py, entity.py, agent.py
│   ├── environment/ — grid.py (spatial source of truth)
│   └── engine/    — plan_result, dispatch_intent, coordinator, dispatcher,
│                    static_dispatcher, simulation
│
├── mrta/          — Multi-Robot Task Allocation, depends only on core   -> mrta/AGENT.md
│                    task, task_source (+ queue/random/scripted/composite),
│                    allocator, fleet_manager
│
├── diagrammes/    — PlantUML sources + PNGs; script_perso.sh watches and regenerates -> diagrammes/AGENT.md
├── main.py               — BROKEN: imported client.control/report, both removed — see TODO.md
├── sim_many_mrta.py      — BROKEN: same reason — see TODO.md
├── sim_many_pibt.py      — BROKEN: imported a concrete PathPlanner from algo/, removed — see TODO.md
├── sim_many_lacam.py     — BROKEN: same reason — see TODO.md
├── sim_many_pibt_plus.py — BROKEN: same reason — see TODO.md
├── TODO.md · README.md · GUIDE.md · CONVENTION.md · CLAUDE.md
└── requirements.txt · LICENSE
```

Every package carries an `__init__.py` re-exporting its public names; the package guide lists
them. `experiments.csv`, `sim_results.csv` and `mrta_results.csv` may sit at the root — all
gitignored outputs.

**Dependency direction** (strict, matches the class diagram):

```
mrta -> core
```

There is currently nothing implementing `PathPlanner` or `AssignmentStrategy`, and nothing above
`mrta` names a concrete one or wires a `TaskDrivenOrchestrator`; see `TODO.md`.

---

## Rules and invariants

Two different things, kept apart on purpose. A **rule** constrains what you may write — breaking
one is a layering bug, and no amount of local convenience justifies it. An **invariant** is a
property the code already guarantees; your change does not have to restate it, but it must not
break it. When in doubt, the class diagram arbitrates.

### Hard rules — never violate these

- **`core/` must never import `mrta/`** — strictly one-directional dependency.
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
  | `diagrammes/Class_Diagram/class_diag_commented.puml` | the architecture, annotated: `core`, `mrta` | `plantuml diagrammes/Class_Diagram/class_diag_commented.puml` |
  | `diagrammes/component_diagram.puml` | packages and the seams between them | `plantuml diagrammes/component_diagram.puml` |
  | `diagrammes/Class_Diagram/class_diag_simplified.puml` | the easiest-to-read rendering | `plantuml diagrammes/Class_Diagram/class_diag_simplified.puml` |

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
| Mission identity belongs to the registry | `TaskDrivenOrchestrator` stamps `task_id` at intake; sources propose missions without one, so several sources cannot collide (`Mission` hashes on `task_id`) |
| No unreachable mission consumes an agent | intake guard + progress watchdog release the assignee and end in `FAILED`, **counted** not dropped |

A few invariants used to live here that named `algo/` classes directly (PIBT's goal-stability
rule, its `-inf` demotion policy, the two allocators' seeded-RNG guarantee) — dropped along with
`algo/` itself rather than kept as a promise nothing currently makes. Whatever implements
`PathPlanner`/`AssignmentStrategy` next should restate the ones that still apply to it.

No invariant currently describes a multi-cell entity: `Zone` filled that role and was removed
once nothing depended on it — see [`core/AGENT.md`](core/AGENT.md).
