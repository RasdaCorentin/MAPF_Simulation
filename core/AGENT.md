# core/ — the engine

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`core/` is the pure simulation engine: entities, the grid they live on, and the tick that
moves them. It has no dependents in the repository right now — `mrta/` (task allocation) was
removed; the `PathPlanner`/`MissionOrchestrator` seams still exist for whatever plugs in next
to do so without the engine noticing.

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
`manhattan_distance()` is the one Manhattan-distance helper for the whole codebase — kept here so
any future caller (a planner, an allocator) uses the same one instead of carrying its own copy.

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

### `Orientation` — `core/entities/orientation.py`
```python
class Orientation(Enum):
    NORTH = "N"
    EAST  = "E"
    SOUTH = "S"
    WEST  = "W"
```
Cardinal heading. Exists for a future League-of-Robot-Runners-style export (PlanViz reads a
per-agent heading and discrete `R`/`F`/`W` actions per tick) — see the note on `Agent` below.

---

### `Agent` — `core/entities/agent.py`
```python
class Agent(WorldEntity):
    agent_id:    int        # alias of entity_id
    steps_taken: int
    orientation: Orientation  # defaults to Orientation.NORTH at construction
    blocks_movement = True  # (passed to super().__init__)
    def move_to(new_position: Coordinates2D)     # updates position + steps_taken
    def rotate_to(new_orientation: Orientation)   # updates orientation only — not a step
    def __eq__ / __hash__                        # based on agent_id — hashable, usable as a dict key
```
`agent_id` is immutable -> stable hash. Meant to be used as a dict key wherever a planner
tracks per-agent state — goals, priorities, reservations; PIBT did exactly this before `algo/`
was removed (see `TODO.md`).
Constructor: `Agent(agent_id, position)` — no strategy of its own, movement is always delegated to the `PathPlanner`.

⚠ **No `PathPlanner` sets `orientation` today.** `WorldEngine.advance_time_step()` applies it from
`StepOutcome.orientations` when a planner populates that dict (see `StepOutcome` below), but no
planner does yet, so every `Agent` keeps its default heading in practice. There is also no
rotate-XOR-move constraint: nothing stops a planner from changing both `position` and
`orientation` for the same agent in the same tick — LoRR semantics (an agent does one thing per
tick) are not enforced, `_validate_plan()` does not check for it.

---

### `Objective` — `core/entities/objective.py`
```python
class Objective(WorldEntity):
    - _assignee: Agent | None
    --
    + assignee: Agent | None              # read-only property over _assignee
    + attach_to(agent: Agent) : void
```
A goal, not an obstacle. `Objective` is a `WorldEntity` like any other — placed and indexed the
same way, no special taxonomy needed — carrying no state of its own beyond binding to exactly one
`Agent`. `attach_to()` is its only mutator. First removed in `56344f8` when goals were flattened to a
plain `dict[int, Coordinates2D]`; reinstated once `AssignmentManifest.goals` needed to carry a
per-goal assignee again rather than an implicit agent_id key — see `AssignmentManifest` below.

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
    positions:    dict[int, Coordinates2D]   # agent_id -> next Coordinates2D (universal contract)
    moves:        dict[int, tuple]           # agent_id -> (from, to)          (universal contract)
    order:        list[int]                  # agent_ids in priority order        (optional diagnostic)
    inheritance:  list[tuple]                # (pusher_id, pushed_id)             (optional diagnostic)
    priorities:   dict[int, float]           # agent_id -> priority               (optional diagnostic)
    orientations: dict[int, Orientation]     # agent_id -> next Orientation       (optional, unset by every planner today)
```
DTO returned by every `PathPlanner.plan()` call. `positions`/`moves` are the contract every planner fills; the rest are diagnostics a planner may leave empty if it has nothing to report there — PIBT was the one implementation that populated all three, before `algo/` was removed (see `TODO.md`). `orientations` follows the same sparse convention as `positions`: an agent absent from it keeps its current heading. Keys are `agent_id` integers so it can cross package boundaries without exposing `Agent` objects.

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
    goals:      list[Objective]   # every Objective wanted this tick, each attach_to()'d already
    priorities: dict[int, float]  # agent_id -> allocation priority (optional per agent)
```
Immutable carrier of the **absolute** allocation state for one tick (complete state, not deltas). Produced by a `MissionOrchestrator`, consumed by `PathPlanner.plan()`. It is the *only* channel for goals/priorities — there is no external mutation of the planner, which keeps allocation and navigation (whatever implements each seam) decoupled and gives an auditable per-tick record. `priorities` stays agent_id-keyed; a planner recovers "who wants what" by reading each `Objective.assignee.agent_id`, not by indexing `goals` — there is no dict-style lookup any more.

---

### `PathPlanner` — `core/engine/coordinator.py`
```python
class PathPlanner(ABC):
    @abstractmethod
    def plan(self, agents: list[Agent], grid: Grid2D, intent: AssignmentManifest) -> StepOutcome: ...
```
The single-method interface for every MAPF algorithm. Goals and priorities arrive only through `intent`; a priority-less planner (e.g. random walk) simply ignores `intent.priorities`. Any `PathPlanner` can therefore be paired with any `MissionOrchestrator`.

---

### `MissionOrchestrator` — `core/engine/dispatcher.py`
```python
class MissionOrchestrator(ABC):
    @abstractmethod
    def assign_missions(self, agents: list[Agent], grid: Grid2D, step: int) -> AssignmentManifest: ...
```
Pre-planning hook: `WorldEngine.advance_time_step()` runs the orchestrator (if attached) **before** `plan()` and passes the returned manifest to it, so goals are never stale by construction. It never touches the planner. Living in `core` lets `WorldEngine` own the tick order (assign missions → plan) without the engine importing whatever implements this seam. **There is no concrete `MissionOrchestrator` in the repository right now** — `TaskDrivenOrchestrator` (`mrta`) was the one implementation, removed along with the rest of `mrta/` (task allocation, out of scope for this repo now); `FixedGoalDispatcher` (`core/engine/static_dispatcher.py`) filled the role before that, but was removed once `AssignmentManifest.goals` became `list[Objective]`: building an `Objective` needs a live `Agent` to `attach_to()`, which a fixed-at-construction dispatcher does not have until `assign_missions()` runs, so it could not be trivially adapted.

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
    exporter:     Exporter | None              # optional — records each tick, see below
    last_intent:  AssignmentManifest           # the manifest used by the last step (auditable)

    __init__(grid, planner, orchestrator=None, exporter=None)
    register_agent(agent)              # place + append
    spawn_static_obstacle(entity)      # append + place immediately if appear_at <= current_step
    advance_time_step() -> StepOutcome # spawn -> assign missions -> plan -> validate -> lift -> place -> rotate -> export
    close()                            # exporter.flush() if attached — call once, after the run ends
    _validate_plan(result)             # rejects an inapplicable plan BEFORE any mutation
```

⚠ **`exporter`/`close()`/`Exporter` are diagram-only — no code behind them yet.** `Exporter`
(`core/engine/exporter.py`, not yet written) is a third abstract seam alongside `PathPlanner` and
`MissionOrchestrator`, but silent by default: `WorldEngine` works with `exporter=None`, and
`advance_time_step()` simply skips the `record()` call when unset — unlike `planner`, this one is
not mandatory. `record(step, agents, grid, outcome)` runs once per tick, after the move/rotate
phases; `flush()` runs once, whenever the caller decides the run is over (`WorldEngine.close()`),
not per tick. Concrete exporters (e.g. one producing a PlanViz-readable run) live in `export/`, a
new dependent package with the same one-directional shape as `pibt/` — see
`Class_Diagram/Export/`. A caller wanting a logged run just constructs
`WorldEngine(grid, planner, exporter=SomeExporter(...))` directly; there is no decorator class.

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
# 7. Rotate: agent.rotate_to(orientation) for every agent in result.orientations — no lift/place
#    needed, orientation is not grid-indexed
# 8. Export (optional, not yet implemented): self.exporter.record(current_step, agents, grid, result)
#    if exporter is not None
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
