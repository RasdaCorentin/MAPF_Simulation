# core/ — the engine

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`core/` is the pure simulation engine: entities, the grid they live on, and the tick that
moves them. It imports **nothing** from `mrta/` — the dependency is strictly one-directional,
which is what lets an algorithm or an allocator be swapped without the engine noticing.

### `Coordinates2D` — `core/entities/position.py`
```python
@dataclass(frozen=True)
class Coordinates2D:
    x: int
    y: int
    def __add__(self, other: Coordinates2D) -> Coordinates2D  # vector addition

def manhattan_distance(a: Coordinates2D, b: Coordinates2D) -> int   # module-level helper
```
Hashable (frozen). Used as a dict key in `Grid2D._agents` and `Grid2D._static`.
`manhattan_distance()` is the one Manhattan-distance helper for the whole codebase — `mrta`'s
watchdog calls it directly instead of each caller carrying its own copy.

---

### `WorldEntity` — `core/entities/entity.py`
```python
class WorldEntity:
    entity_id:       int
    position:        Coordinates2D
    appear_at:       int   # step at which the entity spawns (0 = immediate)
    blocks_movement: bool  # True -> cell impassable for agents
    scale:           int   # RESERVED — stored, never read (see below)
    is_active:       bool  # property, True by default
```
Common base for any entity placed on the grid. Blocking obstacles are created with `WorldEntity(id, pos, blocks_movement=True)` — **no dedicated subclass needed**. Every entity is indexed at its single `position`; there is currently no multi-cell entity (`Zone` filled that role and was removed — see below).

⚠ **`scale` is still reserved and read nowhere in the repo.** It would express a movement
*footprint* — "how much room does it need to move?" — and would force `Grid2D`, `is_blocked`,
`WorldEngine._validate_plan` and a planner's candidate generation to change together. It is
assigned in `__init__` and nothing else: do not write code that assumes it works.

**`Zone` was removed.** A named, multi-cell region (`Zone(entity_id, name, cells, appear_at=0)`,
indexed at every cell it covered) used to live at `core/entities/zone.py`. It never blocks
movement and nothing in the codebase depends on it any more, so it was deleted outright rather
than kept stale — along with the `cells` property on `WorldEntity` and the per-cell iteration in
`Grid2D.place()` / `unindex()` / `all_of_kind()` that existed only to support it. Reinstating a
multi-cell entity means reintroducing both pieces together.

---

### `Agent` — `core/entities/agent.py`
```python
class Agent(WorldEntity):
    agent_id:    int        # alias of entity_id
    steps_taken: int
    blocks_movement = True  # (passed to super().__init__)
    def move_to(new_position: Coordinates2D)   # updates position + steps_taken
    def __eq__ / __hash__                      # based on agent_id — hashable, usable as a dict key
```
`agent_id` is immutable -> stable hash. Meant to be used as a dict key wherever a planner
tracks per-agent state — goals, priorities, reservations; PIBT did exactly this before `algo/`
was removed (see `TODO.md`).
Constructor: `Agent(agent_id, position)` — no strategy of its own, movement is always delegated to the `PathPlanner`.

---

### `Grid2D` — `core/environment/grid.py`
```python
class Grid2D:
    width: int
    height: int
    _agents: dict[Coordinates2D, Agent]
    _static: dict[Coordinates2D, list[WorldEntity]]

    is_within_bounds(position) -> bool
    is_blocked(position) -> bool          # True if an agent OR an active blocking entity occupies it
    place(entity: WorldEntity)            # indexes it at entity.position; raises if out of bounds
                                          # or if an agent cell is already taken
    unindex(entity: WorldEntity)
    agent_at(position) -> Agent | None
    entities_at(position, kind=None) -> list[WorldEntity]   # filters is_active=True on _static
    all_of_kind(kind=None) -> list[WorldEntity]
```
Each entity is indexed at exactly one cell, its `position` — there is no multi-cell entity left
in the codebase (see the `Zone` removal note above), so `all_of_kind()` no longer needs to
de-duplicate.

---

### `StepOutcome` — `core/engine/plan_result.py`
```python
@dataclass(frozen=True)
class StepOutcome:
    positions:   dict[int, Coordinates2D]   # agent_id -> next Coordinates2D (universal contract)
    moves:       dict[int, tuple]           # agent_id -> (from, to)          (universal contract)
    order:       list[int]                  # agent_ids in priority order        (optional diagnostic)
    inheritance: list[tuple]                # (pusher_id, pushed_id)             (optional diagnostic)
    priorities:  dict[int, float]           # agent_id -> priority               (optional diagnostic)
```
DTO returned by every `PathPlanner.plan()` call. `positions`/`moves` are the contract every planner fills; the rest are diagnostics a planner may leave empty if it has nothing to report there — PIBT was the one implementation that populated all three, before `algo/` was removed (see `TODO.md`). Keys are `agent_id` integers so it can cross package boundaries without exposing `Agent` objects.

**Frozen**, like every value crossing a package boundary in this project: a caller can hold onto
the object `WorldEngine.advance_time_step()` returned without the engine being able to rewrite it
later — the guarantee rests on the type rather than on the convention that planners build the
object whole and nobody writes to it afterwards. The contained dicts are not deep-frozen — this
is a guard, not a proof.

---

### `AssignmentManifest` — `core/engine/dispatch_intent.py`
```python
@dataclass(frozen=True)
class AssignmentManifest:
    goals:      dict[int, Coordinates2D]   # agent_id -> target (absolute, this tick)
    priorities: dict[int, float]           # agent_id -> allocation priority (optional per agent)
```
Immutable, `agent_id`-keyed carrier of the **absolute** allocation state for one tick (complete state, not deltas). Produced by a `MissionOrchestrator`, consumed by `PathPlanner.plan()`. It is the *only* channel for goals/priorities — there is no external mutation of the planner, which keeps allocation (`mrta`) and navigation (whatever implements `PathPlanner`) decoupled and gives an auditable per-tick record.

---

### `PathPlanner` — `core/engine/coordinator.py`
```python
class PathPlanner(ABC):
    @abstractmethod
    def plan(self, agents: list[Agent], grid: Grid2D, intent: AssignmentManifest) -> StepOutcome: ...
```
The single-method interface for every MAPF algorithm. Goals and priorities arrive only through `intent`; a priority-less planner (e.g. random walk) simply ignores `intent.priorities`. Any `PathPlanner` can therefore be paired with any `MissionOrchestrator`.

---

### `MissionOrchestrator` / `FixedGoalDispatcher` — `core/engine/dispatcher.py`, `static_dispatcher.py`
```python
class MissionOrchestrator(ABC):
    @abstractmethod
    def assign_missions(self, agents: list[Agent], grid: Grid2D, step: int) -> AssignmentManifest: ...

class FixedGoalDispatcher(MissionOrchestrator):
    def __init__(self, goals: dict[int, Coordinates2D], priorities: dict[int, float] | None = None): ...
    def assign_missions(self, agents, grid, step) -> AssignmentManifest   # same fixed manifest every tick
```
Pre-planning hook: `WorldEngine.advance_time_step()` runs the orchestrator (if attached) **before** `plan()` and passes the returned manifest to it, so goals are never stale by construction. It never touches the planner. Living in `core` lets `WorldEngine` own the tick order (assign missions → plan) **without importing `mrta`** — the same dependency-inversion seam as `PathPlanner`. `TaskDrivenOrchestrator` (`mrta`) and `FixedGoalDispatcher` are the concrete orchestrators; use `FixedGoalDispatcher` for fixed-goal scenarios that need no task allocation.

---

### `WorldEngine` — `core/engine/simulation.py`
```python
class WorldEngine:
    grid:         Grid2D
    agents:       list[Agent]
    entities:     list[WorldEntity]
    _pending:     list[WorldEntity]
    current_step: int
    planner:      PathPlanner              # mandatory — no per-agent fallback
    orchestrator: MissionOrchestrator | None   # optional — produces this tick's manifest
    last_intent:  AssignmentManifest           # the manifest used by the last step (auditable)

    __init__(grid, planner, orchestrator=None)
    register_agent(agent)              # place + append
    spawn_static_obstacle(entity)      # append + place immediately if appear_at <= current_step
    advance_time_step() -> StepOutcome # spawn -> assign missions -> plan -> validate -> lift -> place
    _validate_plan(result)             # rejects an inapplicable plan BEFORE any mutation
```

**`advance_time_step()` logic** — `current_step += 1` runs **first**, so `appear_at` is compared
against the already-incremented step (an entity with `appear_at=1` spawns on the first
`advance_time_step()`):
```python
# 1. Spawn deferred entities whose appear_at step has been reached
# 2. Assign missions: intent = self.orchestrator.assign_missions(...) if orchestrator else AssignmentManifest()  (empty)
#    stored in self.last_intent
# 3. Coordinated planning (mandatory): result = self.planner.plan(self.agents, self.grid, intent)
# 4. Validate: self._validate_plan(result) — raises before the grid is touched
# 5. Lift:  grid.unindex(agent) for every agent whose target differs from its position
# 6. Place: agent.move_to(target) then grid.place(agent)
#    Return result — a caller reads diagnostics from it without importing the planner's package
```
The `assign missions → plan` order is owned by `advance_time_step()`, so a caller cannot plan on stale goals. Movement is applied by `advance_time_step()` itself (lift-then-place) to handle simultaneous swaps — `agent.move_to` is never called outside this transaction, so `Agent.position` and the grid index stay in sync.

**`_validate_plan()` rejects three things**, before any mutation, so the lift/place transaction cannot
fail halfway and strand agents off the grid:
1. **two agents claiming one cell** — checked for *every* agent, stationary ones included, so a
   mover cannot target a cell a stationary agent is keeping;
2. **a target off the grid** (`not grid.is_within_bounds`);
3. **a target under an active blocking entity**.

Checks 2 and 3 are **deliberately skipped for agents that do not move**. An obstacle spawning via
`appear_at` onto an already-occupied cell would otherwise be reported as a planning error, which
it is not — the planner never proposed that overlap.

---

---

## Notes parked for the engine diagram

> These were deliberately left **out of the class diagram** to keep it readable. They are
> true and they matter, but each belongs in a diagram that does not exist yet.
> **Delete an entry the moment its diagram carries it.**

- `WorldEngine._validate_plan()` skips the off-grid and blocked-cell checks for agents that do not
  move, so an obstacle spawning via `appear_at` onto an occupied cell is not reported as a
  planning error.
- `Grid2D.entities_at` / `all_of_kind` and `WorldEngine._validate_plan` were dropped from the
  class diagram as secondary; they remain part of the API.
