# Renaming proposal — classes & functions

**Status: proposal only, nothing here has been applied to the code yet.** This is the
brainstorming step that has to happen before any rename touches `_model.iuml`/the class
diagrams (which the project's diagram-governance rule requires to be validated *before* the
matching code change — see `diagrammes/AGENT.md`). Nothing in this document is binding.

**Scope**: `core/`, `mrta/`, `algo/` — every `.py` file except `__init__.py` (pure re-exports).
Internal, non-re-exported modules (`pibt_core.py`, `lacam_config.py`, `push_and_swap.py`,
`_scratch.py`, `reservation_table.py`, `priority_manager.py`) are included: they carry real
production logic and deserve names as much as the public API does.

---

## 0. Raw inventory

Every class in scope, followed by its own methods (one per line, tab-indented). Module-level
functions (no enclosing class) are grouped under a `(module-level)` marker. This is the literal
list the renaming proposals below work from.

### core/entities/position.py
```
Position
	__add__
	__repr__
```

### core/entities/entity.py
```
WorldEntity
	__init__
	cells
	active
```

### core/entities/agent.py
```
Agent
	__init__
	agent_id
	move_to
	__eq__
	__hash__
	__repr__
```

### core/entities/zone.py
```
Zone
	__init__
	cells
	contains
	__repr__
```

### core/environment/grid.py
```
Grid
	__init__
	is_valid
	is_blocked
	place
	remove
	get_agent_at
	get_entities_at
	get_all
	__repr__
```

### core/engine/coordinator.py
```
Coordinator
	plan
```

### core/engine/dispatcher.py
```
Dispatcher
	dispatch
```

### core/engine/dispatch_intent.py
```
DispatchIntent
```

### core/engine/plan_result.py
```
PlanResult
```

### core/engine/simulation.py
```
Simulation
	__init__
	add_agent
	add_object
	_validate
	step
	__repr__
```

### core/engine/static_dispatcher.py
```
StaticDispatcher
	__init__
	dispatch
```

### mrta/task.py
```
TaskState
Task
	__eq__
	__hash__
```

### mrta/task_source.py
```
TaskSource
	poll
```

### mrta/queue_task_source.py
```
QueueTaskSource
	__init__
	push
	push_many
	poll
```

### mrta/random_task_source.py
```
RandomTaskSource
	__init__
	poll
```

### mrta/scripted_task_source.py
```
ScriptedTaskSource
	__init__
	poll
```

### mrta/composite_task_source.py
```
CompositeTaskSource
	__init__
	poll
```

### mrta/allocator.py
```
Allocator
	allocate
```

### mrta/fleet_manager.py
```
FleetManager
	__init__
	dispatch
	set_priority
	_complete
	_watchdog
	_prune
	_intake
	_allocate
	_build_intent
	_by_eligibility
	_is_obstructed
	_manhattan
```

### algo/allocation/easiest_allocator.py
```
EasiestAllocator
	allocate
	_manhattan
```

### algo/allocation/kdtree_greedy_allocator.py
```
KDTreeGreedyAllocator
	__init__
	allocate
	_nearest_free
```

### algo/allocation/random_allocator.py
```
RandomAllocator
	__init__
	allocate
```

### algo/coordination/lacam_config.py
```
HighLevelNode
	__init__
(module-level)
	is_goal_config
	config_key
```

### algo/coordination/lacam_coordinator.py
```
(module-level)
	_manhattan
LaCAMCoordinator
	__init__
	_goal_key
	_next_constraint
	_backtrack
	_solve
	_generate_successor
	plan
```

### algo/coordination/pibt_coordinator.py
```
GoalReachedPolicy
PIBTCoordinator
	__init__
	_apply_intent
	plan
```

### algo/coordination/pibt_core.py
```
(module-level)
	_h
	_pibt
	run_pibt_pass
```

### algo/coordination/pibt_plus_coordinator.py
```
(module-level)
	_manhattan
	_build_scratch
PIBTPlusCoordinator
	__init__
	_goal_key
	_run_pibt_phase
	_solve
	plan
```

### algo/coordination/priority_manager.py
```
PriorityManager
	__init__
	update
	get_priority
	get_base
	set_base
```

### algo/coordination/push_and_swap.py
```
(module-level)
	_manhattan
	_passable
PushAndSwapCoordinator
	__init__
	_bfs
	_try_push
	plan
	_advance_relocation
	_result
```

### algo/coordination/random_walk.py
```
RandomWalkCoordinator
	plan
```

### algo/coordination/reservation_table.py
```
ReservationTable
	__init__
	reserve
	release
	get_reserving_agent
	get_reservation
	clear
```

### algo/coordination/_scratch.py
```
(module-level)
	build_scratch_grid
```

---

## 1. Ground rules for this pass

The starting proposal (quoted by the user, not yet validated) got several things right — mapping
each package to a business story (*world* → *who does what* → *how they get there without
colliding*) is a real improvement over the current somewhat academic vocabulary. Before extending
it to the full inventory, four corrections to the starting premise:

1. **Casing: keep `snake_case` for functions/methods, `PascalCase` for classes.** The example
   proposed `camelCase` (`advanceTimeStep`, `assignPendingMissions`...). That's a JS/Java
   convention; this is a Python codebase, PEP 8 throughout, and every attribute/method that
   *isn't* renamed (`dataclass` fields, `__init__`, existing helpers) stays `snake_case`. Adopting
   `camelCase` for renamed names only would leave the codebase in two styles at once for zero
   architectural gain — this document renames the *words*, not the *case convention*. All
   proposals below are `snake_case`.

2. **The real motivation isn't "hardware-agnostic naming."** The example frames this rename as a
   consequence of deleting `client/` ("removing the rendering layer lets the engine's names go
   generic"). That doesn't hold up: `core`/`mrta`/`algo` were never coupled to `client/`
   vocabulary in the first place — `DispatchIntent`/`PlanResult` are already described as "the
   only channel" between engine and business logic, and `client/`'s own classes
   (`PygameFrontend`, `Renderer`, `StepSnapshot`...) had *already* absorbed all the
   presentation-specific naming, which is exactly why deleting that package didn't touch a single
   name in `core`/`mrta`/`algo`. The actual value of a renaming pass here is **narrative
   coherence** — reading `WorldEngine.advance_time_step()` calling
   `MissionOrchestrator.assign_pending_missions()` should tell the story of one tick without a
   comment — not decoupling, which already happened structurally. Worth naming the real reason,
   since it changes what "success" looks like: not "no more mentions of pygame" (there never
   were any) but "a stranger can read the call chain and follow the story."

3. **No interface/implementation name collisions.** The example renames both the abstract
   `Dispatcher` *and* its concrete `FleetManager` to `MissionOrchestrator`, and both
   `EasiestAllocator` *and* the stub `KDTreeGreedyAllocator` to `ProximityBasedAssignment` — losing
   the third allocator, `RandomAllocator`, entirely. Each `Strategy` (per the class diagram's own
   stereotype) keeps **one** interface name; every concrete subclass gets a name that specializes
   it, never reuses it verbatim. Section 3 below fixes this.

4. **Two names need your explicit sign-off before going further, not a silent rename:**
   `Agent` and the four algorithm classes (`PIBTCoordinator`, `PIBTPlusCoordinator`,
   `LaCAMCoordinator`, `PushAndSwapCoordinator`). "Agent" is the standard term across the entire
   MAPF literature this project implements (Okumura et al.'s PIBT paper, LaCAM, ...) — renaming it
   to `MobileUnit`/`AutonomousRobot` reads more generic but severs that link for anyone
   cross-referencing the papers `algo/AGENT.md` already cites. Same reasoning for keeping the
   algorithm names (`PIBT`, `LaCAM`, push-and-swap) *inside* the class name rather than erasing
   them behind `CollisionResolver`/`PathfindingStrategy` — see §2 for the proposed compromise
   (keep the algorithm identity, unify the suffix).

---

## 2. Core & environment — the physical/temporal substrate

| Old | New | Note |
|---|---|---|
| `Simulation` | `WorldEngine` | matches the "one tick of the world" role already documented on the class |
| `Simulation.step()` | `advance_time_step()` | |
| `Simulation.add_agent()` | `register_agent()` | keeps "agent" per §1.4; drop "active" — every registered agent starts active by construction, the word adds nothing |
| `Simulation.add_object()` | `spawn_static_obstacle()` | matches the actual call sites (obstacles, not arbitrary objects) |
| `Simulation._validate()` | `_validate_plan()` | clarifies *what* is validated (a `PlanResult`, pre-mutation) |
| `Grid` | `SpatialIndex` | not `Workspace`/`SpatialEnvironment` — the class docstring and the diagram note are explicit that it's *"a spatial index, not a store"*; `SpatialIndex` states that responsibility instead of implying it owns the entities |
| `Grid.is_valid()` | `is_within_bounds()` | |
| `Grid.is_blocked()` | `is_blocked()` | already accurate, keep |
| `Grid.place()` | `place()` | already accurate, keep |
| `Grid.remove()` | `unindex()` | pairs with `place()`→index; avoids implying deletion of the entity itself (it isn't — see the diagram's own comment on `Grid o-- WorldEntity`) |
| `Grid.get_agent_at()` | `agent_at()` | drop the redundant `get_` prefix (Python convention, not Java bean-style) |
| `Grid.get_entities_at()` | `entities_at()` | same |
| `Grid.get_all()` | `all_of_kind()` | current name is too vague for what it does (dedup by `id()`, optional `kind` filter) |
| `Position` | `Coordinates2D` | example's choice, plain and unambiguous |
| `WorldEntity` | `SpatialEntity` | not `PhysicalEntity` — nothing here models mass/velocity/physics, only "occupies this cell(s), optionally blocks movement"; `SpatialEntity` names that precisely |
| `WorldEntity.active` (property) | `is_active` | property, not a method — keep it a property, just rename for the boolean-prefix convention already used elsewhere (`is_valid`, `is_blocked`) |
| `Agent` | *(kept — see §1.4)* | |
| `Agent.move_to()` | `move_to()` | already accurate, keep |
| `Agent.agent_id` (property) | *(kept)* | already accurate |
| `Zone` | `NamedRegion` | conveys "operator-addressable area," matches the existing note on the class |
| `Zone.contains()` | `contains()` | already accurate, keep |
| `PlanResult` | `StepOutcome` | not `MovementDirectives` — the DTO carries `order`/`inheritance`/`priorities` (the PIBT audit trail), not just positions/moves; "movement directives" undersells the diagnostic half of the contract |
| `DispatchIntent` | `AssignmentManifest` | example's choice, accurate |
| `Coordinator` | `PathPlanner` | not `CollisionResolver` — `RandomWalkCoordinator` doesn't resolve anything, it's a naive baseline; "resolver" implies active conflict-solving that not every implementation does. `PathPlanner` covers the whole family honestly |
| `Coordinator.plan()` | `plan()` | already accurate, keep |
| `Dispatcher` | *(see §3 — do not merge with `FleetManager`)* | |
| `StaticDispatcher` | `FixedGoalDispatcher` | states what makes it "static": one goal set, fixed at construction |

---

## 3. Navigation & coordination — how agents get there without colliding

Keeping algorithm names (§1.4) but unifying the suffix so the family reads as one hierarchy:
`XCoordinator` → `XPlanner`.

| Old | New | Note |
|---|---|---|
| `RandomWalkCoordinator` | `RandomWalkPlanner` | |
| `PIBTCoordinator` | `PibtPlanner` | |
| `PIBTPlusCoordinator` | `PibtPlusPlanner` | **currently in no diagram** — flagged in the earlier consistency audit |
| `LaCAMCoordinator` | `LacamPlanner` | **currently in no diagram** |
| `PushAndSwapCoordinator` | `PushAndSwapPlanner` | **currently in no diagram**, and not re-exported from `algo/__init__` today (internal, used only as PIBT+'s phase 2) — a rename doesn't change that visibility, just naming it consistently with its siblings |
| `PIBTCoordinator.goals` | `goals` | already accurate, keep |
| `PIBTCoordinator._apply_intent()` | `_seed_goals_and_priorities()` | states what it does: re-seeds from intent without clobbering dynamic drift |
| `GoalReachedPolicy` (enum) | `GoalHoldPolicy` | `TRANSIENT`/`PERMANENT` members are already clear, keep as-is |
| `ReservationTable` | `CellReservationLedger` | not `SpaceTimeRegistry` — the table is scoped to a *single* planning pass (one `step()`'s worth of reservations, not a multi-timestep space-time reservation as in CBS-style planners); "space-time" overstates what it actually tracks |
| `ReservationTable.reserve()` | `reserve_cell()` | |
| `ReservationTable.release()` | `release_cell()` | |
| `ReservationTable.get_reserving_agent()` | `agent_holding()` | drop `get_` prefix |
| `ReservationTable.get_reservation()` | `reservation_for()` | drop `get_` prefix |
| `ReservationTable.clear()` | `clear()` | already accurate, keep |
| `PriorityManager` | `PriorityTracker` | not `UnitRankTracker` — keeps the domain word "priority" (already used everywhere: `DispatchIntent.priorities`, `Task.priority`) rather than introducing a synonym ("rank") for the same concept |
| `PriorityManager.update()` | `decay_priorities()` | states the actual effect (per `algo/AGENT.md`: priorities decay every step so no agent starves) rather than the generic "update" |
| `PriorityManager.get_priority()` | `priority_of()` | |
| `PriorityManager.get_base()` | `base_of()` | |
| `PriorityManager.set_base()` | `set_base()` | already accurate, keep |
| `HighLevelNode` (LaCAM) | `LacamSearchNode` | ties the name to its owning algorithm, since it's LaCAM-specific search-tree state |
| `HighLevelNode.config` | `config` | keep — `Config = dict[int, Position]` alias is already a reasonable domain name |

### Module-level functions (`algo/coordination/`)

| Old | New | Note |
|---|---|---|
| `lacam_config.is_goal_config()` | `is_goal_config()` | already accurate, keep |
| `lacam_config.config_key()` | `config_key()` | already accurate, keep |
| `pibt_core._h()` | `_heuristic_distance()` | single-letter name, only reason it's here at all |
| `pibt_core._pibt()` | `_pibt_step()` | disambiguates from the module/algorithm name itself |
| `pibt_core.run_pibt_pass()` | `run_pibt_pass()` | already accurate, keep — this is the one name in the whole inventory that best demonstrates the "verb + what it does" goal |
| `_scratch.build_scratch_grid()` | `build_scratch_grid()` | already accurate, keep. Note: **not dead code** despite the leading underscore — see the earlier consistency audit; `_` here means "package-private," not "draft" |
| `_manhattan()` × 6 (`FleetManager`, `EasiestAllocator`, `lacam_coordinator`, `pibt_plus_coordinator`, `push_and_swap`) | `manhattan_distance(a, b)` — **one shared function**, not six copies | see §4 |

---

## 4. MRTA — who does what

**Correction to the starting proposal (§1.3):** the abstract `Dispatcher` and its two concrete
implementations (`FleetManager`, `StaticDispatcher`) cannot share one name — that erases the
Strategy split the class diagram documents on purpose ("any `Dispatcher` pairs with any
`Coordinator`"). Same for `Allocator`'s three concrete strategies, which the original proposal
collapsed into one name and, in doing so, dropped `RandomAllocator` from the exercise entirely.

| Old | New | Note |
|---|---|---|
| `Dispatcher` (abstract) | `MissionOrchestrator` | the interface — "decides WHERE each robot goes" |
| `Dispatcher.dispatch()` | `assign_missions()` | |
| `FleetManager` (concrete) | `TaskDrivenOrchestrator` | *not* `MissionOrchestrator` — that name is now the interface's |
| `FleetManager.set_priority()` | `set_mission_priority()` | |
| `FleetManager._complete()` | `_finalize_arrived_missions()` | marks arrived missions DONE |
| `FleetManager._watchdog()` | `_release_stalled_assignees()` | progress watchdog: releases an assignee stuck for `patience` steps |
| `FleetManager._prune()` | `_archive_terminal_missions()` | drops DONE/FAILED missions from the active set |
| `FleetManager._intake()` | `_intake_new_missions()` | pulls from the source, rejects off-grid/obstructed targets at the door |
| `FleetManager._allocate()` | `_run_allocation_pass()` | |
| `FleetManager._build_intent()` | `_compile_assignment_manifest()` | mirrors `DispatchIntent` → `AssignmentManifest` |
| `FleetManager._by_eligibility()` | `_filter_eligible_units()` | |
| `FleetManager._is_obstructed()` | `_target_is_unreachable()` | |
| `FleetManager._manhattan()` | *(removed — use the shared `manhattan_distance()`, §3)* | |
| `Task` | `Mission` | example's choice |
| `Task.task_id` | `mission_id` | |
| `Task.target` | `target` | already accurate, keep |
| `Task.assignee` | `assignee` | already accurate, keep |
| `Task.eligible` | `eligible_unit_ids` | states what the `frozenset[int]` actually holds |
| `Task.best_distance` | `best_distance_seen` | disambiguates from a static/optimal distance — it's the watchdog's rolling best |
| `Task.last_improvement_step` | `last_improvement_step` | already accurate, keep |
| `TaskState` (enum) | `MissionState` | mirrors `Task` → `Mission`; members (`PENDING`/`ASSIGNED`/`DONE`/`FAILED`) are already clear, keep as-is |
| `TaskSource` (abstract) | `MissionSource` | not `MissionGenerator` — `QueueTaskSource` is externally *pushed*, not generated; "source" covers pushed, scripted, random and composite alike, "generator" only fits one of the four |
| `TaskSource.poll()` | `poll()` | already accurate, keep |
| `QueueTaskSource` | `QueueMissionSource` | |
| `QueueTaskSource.push()` | `push()` | already accurate, keep |
| `QueueTaskSource.push_many()` | `push_many()` | already accurate, keep |
| `RandomTaskSource` | `RandomMissionSource` | |
| `ScriptedTaskSource` | `ScriptedMissionSource` | |
| `CompositeTaskSource` | `CompositeMissionSource` | |
| `CompositeTaskSource.sources` | `sources` | already accurate, keep — and note the real cardinality is `0..*`, not `1..*` (see the earlier consistency audit: `CompositeTaskSource()` with zero sources is valid) |
| `Allocator` (abstract) | `AssignmentStrategy` | the interface — "decides WHO takes which job" |
| `Allocator.allocate()` | `match_missions_to_units()` | |
| `EasiestAllocator` | `NearestUnitAssignment` | linear-scan greedy-nearest |
| `EasiestAllocator._manhattan()` | *(removed — shared `manhattan_distance()`, §3)* | |
| `KDTreeGreedyAllocator` | `KDTreeNearestAssignment` | same greedy-nearest strategy, k-d-tree-accelerated — keep "KDTree" in the name, it's a real algorithmic distinction (indexing structure), not decoration. Still a stub (`NotImplementedError`); **currently in no diagram** |
| `KDTreeGreedyAllocator._nearest_free()` | `_nearest_free_unit()` | |
| `RandomAllocator` | `RandomAssignment` | the baseline, no notion of distance — do not fold into the two proximity-based strategies above |

---

## 5. Cross-cutting cleanup this rename would naturally pick up

Found while building the inventory; not strictly renaming, but adjacent enough that doing them
in the same pass costs nothing extra:

- **`_manhattan()` is copy-pasted six times** (`FleetManager`, `EasiestAllocator`, and
  module-level in `lacam_coordinator.py`, `pibt_plus_coordinator.py`, `push_and_swap.py`). All six
  are identical Manhattan-distance one-liners. Once every one of those files is open for the
  rename anyway, consolidating into a single `manhattan_distance(a, b)` (e.g. in
  `core/entities/position.py`, next to `Position.__add__`) removes five duplicate definitions for
  free.
- **`PlanResult`'s docstring still names the deleted `client/` layer** — it mentions
  `SimulationController`, `StepSnapshot`, `TaskView` and a "core→client boundary" that no longer
  exists. Orthogonal to the rename itself, but worth fixing in the same commit that touches the
  file's class name, so the doc isn't stale twice.
- **`Grid.get_entities_at()` / `Grid.get_all()`** are used throughout production code
  (`FleetManager`, `pibt_core`, `push_and_swap`, `_scratch`) but appear in neither class diagram
  today — flagged in the consistency audit, resurfaced here because the rename touches their
  signatures anyway (`entities_at()`, `all_of_kind()` above).

---

## 6. Open questions before this goes any further

1. **Keep "Agent," or actually adopt a generic name?** (§1.4) Recommendation: keep it — the MAPF
   literature link is real value, not inertia.
2. **Keep algorithm names inside planner classes, or genericize them?** (§1.4, §3) Recommendation:
   keep them, unify only the suffix (`XCoordinator` → `XPlanner`).
3. **`snake_case` vs the originally-proposed `camelCase`?** (§1.1) Recommendation: `snake_case`,
   no ambiguity — this is a Python codebase end to end.
4. Once the above three are settled, the actual mechanical rename should happen **class diagram
   first** (`class_diag_commented.puml`, `class_diag_simplified.puml`, `component_diagram.puml`),
   validated with you, *then* the code — per the standing diagram-governance rule, not the other
   way around.
