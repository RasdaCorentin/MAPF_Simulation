# AGENT.md

> **This is the project map for coding agents. Start here, then read the guide for the package
> you are about to touch. Do not re-explore the tree to answer structural questions.**

**Two companion files are binding and are *not* reproduced here:**
- **`CONVENTION.md`** — repository layout, branch naming, and Conventional Commits. Every commit,
  file name and new file must follow it. Read it before your first commit.
- **`README.md` / `GUIDE.md`** — human-facing overview and guided tour.

The reference for architecture is the class diagram: when this file, the code and the diagram
disagree, **the diagram arbitrates** — see *Rules and invariants*. It and the two object diagrams
are imported below so they are always in context; read them, do not re-derive them.

@diagrammes/_model.iuml

@diagrammes/Object_Diagram/object_diag_mrta.puml

@diagrammes/Object_Diagram/object_diag_static.puml

---

## Package guides — where the class-by-class detail lives

This file holds only what is **cross-cutting**: how to run the thing, the layout, the dependency
direction, the rules and the invariants. Everything about a specific class lives next to it.

| Guide | Covers |
|---|---|
| [`core/AGENT.md`](core/AGENT.md) | `Position`, `WorldEntity`, `Zone`, `Agent`, `Grid`, `PlanResult`, `DispatchIntent`, `Coordinator`, `Dispatcher`, `Simulation` — and the tick |
| [`algo/AGENT.md`](algo/AGENT.md) | PIBT (coordinator, reservations, priorities), random walk, the allocators, how to add a `Coordinator` |
| [`mrta/AGENT.md`](mrta/AGENT.md) | `Task` lifecycle, task sources, `FleetManager`, eligibility, the watchdog, domain vocabulary |
| [`diagrammes/AGENT.md`](diagrammes/AGENT.md) | the binding rule for changing a diagram — read it before touching one |

**Working on one package?** Root + that guide is enough. Changing a *seam* between two — an ABC,
a DTO, an import direction — read both guides and the rules below.

`client/` and `report/` are gone as of this refactor — see `TODO.md` for what that broke
(`main.py`, `sim_many_mrta.py`) and why it was left broken rather than patched.

---

## Running the simulation

`main.py` and `sim_many_mrta.py` currently raise `ImportError` — both depended on
`client.control`/`report`, removed together (see `TODO.md`). What still works, unaffected —
`core/`, `algo/` and `mrta/` were untouched by that removal:

```bash
python sim_many_pibt.py --seeds 2               # headless PIBT benchmark sweep -> sim_results.csv
python sim_many_lacam.py --seeds 2              # same, LaCAM
python sim_many_pibt_plus.py --seeds 2          # same, PIBT+
```
There is currently **no test suite** — these are the de-facto regression checks.

**Runs are reproducible from `--seed` alone** — every allocator owns a seeded RNG rather than
the `random` module's global one. Two runs of the same command must produce identical output;
if they stop doing so, something has reached for global randomness again.

---

## Layout

```
.
├── core/          — pure engine, zero rendering dependency        -> core/AGENT.md
│   ├── entities/  — position.py, entity.py, zone.py, agent.py
│   ├── environment/ — grid.py (spatial source of truth)
│   └── engine/    — plan_result, dispatch_intent, coordinator, dispatcher,
│                    static_dispatcher, simulation
│
├── mrta/          — Multi-Robot Task Allocation, depends only on core   -> mrta/AGENT.md
│                    task, task_source (+ queue/random/scripted/composite),
│                    allocator, fleet_manager
│
├── algo/          — MAPF algorithms                                     -> algo/AGENT.md
│   ├── coordination/ — random_walk, reservation_table, priority_manager,
│   │                   pibt_coordinator
│   └── allocation/   — easiest_allocator (DEFAULT), random_allocator,
│                       kdtree_greedy_allocator (stub)
│
├── diagrammes/    — PlantUML sources + PNGs; script_perso.sh watches and regenerates -> diagrammes/AGENT.md
├── sim_many_pibt.py              — headless PIBT benchmark sweep -> sim_results.csv
├── sim_many_lacam.py             — headless LaCAM benchmark sweep
├── sim_many_pibt_plus.py         — headless PIBT+ benchmark sweep
├── main.py            — BROKEN: imported client.control/report, both removed — see TODO.md
├── sim_many_mrta.py   — BROKEN: same reason — see TODO.md
├── TODO.md · README.md · GUIDE.md · CONVENTION.md · CLAUDE.md
└── requirements.txt · LICENSE
```

Every package carries an `__init__.py` re-exporting its public names; the package guide lists
them. `experiments.csv`, `sim_results.csv` and `mrta_results.csv` may sit at the root — all
gitignored outputs.

**Dependency direction** (strict, matches the class diagram):

```
mrta -> core
algo -> core, mrta
```

There is currently nothing above `algo`/`mrta` — no scripting layer names a concrete
`Coordinator`/`Allocator` or wires a `FleetManager`; see `TODO.md`.

---

## Rules and invariants

Two different things, kept apart on purpose. A **rule** constrains what you may write — breaking
one is a layering bug, and no amount of local convenience justifies it. An **invariant** is a
property the code already guarantees; your change does not have to restate it, but it must not
break it. When in doubt, the class diagram arbitrates.

### Hard rules — never violate these

- **`core/` must never import `algo/` or `mrta/`** — strictly one-directional dependency.
- **`mrta/` must never import `algo/`** — it depends only on `core`.
- **The class diagram is the reference.** When code and `_model.iuml` disagree, the default is to
  change the *code* so the diagram becomes true; amend the model only when it is genuinely wrong.
  The component and object diagrams follow the class diagram, never the reverse.
- **Diamonds follow one rule** (stated at the top of `_model.iuml`): filled for an immutable value
  or a mutable object with a single exclusive owner, hollow for a shared mutable instance.
- **Every diagram change is validated before the code that makes it true is written.** See
  [`diagrammes/AGENT.md`](diagrammes/AGENT.md) for the full rule.
- **Keep the diagrams in sync.** Four sources, each with its own scope:

  | Source | Scope | Regenerate with |
  |---|---|---|
  | `diagrammes/_model.iuml` | the architecture (via `diagrams.puml`) | `plantuml diagrammes/diagrams.puml` |
  | `diagrammes/component_diagram.puml` | packages and the seams between them | `plantuml diagrammes/component_diagram.puml` |
  | `diagrammes/Class_Diagram/class_diag_simplified.puml` | the easiest-to-read rendering | `plantuml diagrammes/Class_Diagram/class_diag_simplified.puml` |
  | `diagrammes/Object_Diagram/object_diag_mrta.puml` | instances after one MRTA tick (French) | `plantuml diagrammes/Object_Diagram/object_diag_mrta.puml` |
  | `diagrammes/Object_Diagram/object_diag_static.puml` | same, static mode (French) | `plantuml diagrammes/Object_Diagram/object_diag_static.puml` |

  `diagrams.puml` renders `_model.iuml` twice — simple and annotated — driven by the `$ANNOTATED`
  preprocessor flag, so the two class diagrams cannot drift apart. Never edit the generated PNGs.
  There is no sequence diagram: `sequence_tick.puml` was dropped — the tick order it showed is
  stated on `Simulation` in the class diagram and in [`core/AGENT.md`](core/AGENT.md).

### Invariants — properties the code already maintains

| Constraint | Detail |
|---|---|
| One agent per cell | `Grid.place()` raises; `Simulation.step()` lifts all movers before placing them |
| `Position` is immutable | frozen dataclass, never mutated |
| `Agent` is hashable | via `agent_id`, usable as a dict key |
| Deferred spawn | `appear_at > 0` -> held in `_pending` until the right step |
| Coordinator is mandatory | `Simulation` refuses to run without one; a dispatcher is optional |
| Obstacle = WorldEntity | `WorldEntity(id, pos, blocks_movement=True)` suffices — no subclass |
| A zone labels ground | `Zone` never blocks movement and is indexed at every cell it covers; `get_all()` returns it once |
| Goal stability | PIBT inserts `loc(i)` first among candidates if `loc(i) == goal(i)` |
| Algorithms have no I/O dependency | `algo/` is pure computation — no rendering, no file access |
| `PlanResult` is the universal contract | every `Coordinator.plan()` returns one; diagnostics are optional |
| `DispatchIntent` decouples allocation from navigation | goals/priorities flow only through the intent; no external mutation of the coordinator, so any Coordinator pairs with any Dispatcher |
| Single mover | only `Simulation.step()` moves agents (lift→`move_to`→place); `agent.move_to` alone must not be called |
| Plans are validated, not rolled back | `Simulation._validate()` rejects an inapplicable `PlanResult` **before** any mutation, so the lift/place transaction cannot fail partially |
| Task identity belongs to the registry | `FleetManager` stamps `task_id` at intake; sources propose tasks without one, so several sources cannot collide (`Task` hashes on `task_id`) |
| `-inf` demotion is reversible by default | "at its goal" is a *state*; under `GoalReachedPolicy.TRANSIENT` (the default) `PIBTCoordinator` saves the overwritten base and restores it as soon as the state stops holding. `PERMANENT`, chosen by the caller at construction for a static goal regime, deliberately never restores it |
| Allocation stays inside the seed | `EasiestAllocator` draws no random numbers; `RandomAllocator` owns its RNG |
| No unreachable task consumes an agent | intake guard + progress watchdog release the assignee and end in `FAILED`, **counted** not dropped |

---

## Still to do on the diagrams

- `Object_Diagram/object_diag_mrta.puml` does not show a `Zone` instance yet.
