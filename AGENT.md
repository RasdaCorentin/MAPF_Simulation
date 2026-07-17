# AGENT.md

> **This is the project map for coding agents. Everything needed to work on this repo is here.**
> **Do not re-explore the tree to answer structural questions — read this file first.**

---

## Running the simulation

```bash
python main.py          # random-walk demo (5 agents, 20 steps)
python demo_pibt.py      # interactive PIBT demo (10 agents, keyboard navigation)
python demo_pibt.py -d   # same, debug mode: terminal print, zero pygame
```

Both open a blocking pygame window (except `-d`). Dependencies: `requirements.txt` + pygame (`pip install pygame`).

---

## Layout

```
.
├── core/                       — pure engine, zero rendering dependency
│   ├── __init__.py             — re-exports: Position, WorldEntity, Agent, Grid, Simulation,
│   │                             Coordinator, PriorityBasedCoordinator, PlanResult, Dispatcher
│   ├── entities/
│   │   ├── position.py         — Position (frozen dataclass, hashable, +)
│   │   ├── entity.py           — WorldEntity (base, blocks_movement, appear_at, scale)
│   │   └── agent.py            — Agent (hashable via agent_id, blocks_movement=True)
│   ├── environment/
│   │   └── grid.py             — Grid (spatial source of truth)
│   └── engine/
│       ├── plan_result.py      — PlanResult (DTO returned by Coordinator.plan())
│       ├── coordinator.py      — Coordinator / PriorityBasedCoordinator (ABCs)
│       ├── dispatcher.py       — Dispatcher (ABC: pre-planning hook run by Simulation.step)
│       └── simulation.py       — Simulation (engine, coordinator mandatory, dispatcher optional)
│
├── client/                     — pygame rendering, depends only on core
│   ├── __init__.py             — re-exports: Renderer, PIBTRenderer, PIBTInteractiveRenderer, StepSnapshot
│   ├── renderer.py             — Renderer (generic pygame loop, read-only view of Simulation)
│   ├── pibt_renderer.py        — PIBTRenderer (extends Renderer: goals, priorities overlay)
│   └── pibt_interactive_renderer.py — PIBTInteractiveRenderer (history + keyboard navigation)
│
├── mrta/                        — Multi-Robot Task Allocation, depends only on core
│   ├── __init__.py              — re-exports: Task, TaskState, TaskSource, Allocator, FleetManager
│   ├── task.py                  — TaskState (enum), Task (dataclass)
│   ├── task_source.py           — TaskSource (ABC: poll(current_step) -> list[Task])
│   ├── allocator.py             — Allocator (ABC: allocate(pending, free, grid) -> dict[Task, Agent])
│   └── fleet_manager.py         — FleetManager (dispatch loop: complete -> intake -> allocate)
│
├── algo/                        — MAPF algorithms, depends on core (and mrta for allocation)
│   ├── __init__.py              — re-exports: PIBTCoordinator, RandomWalkCoordinator,
│   │                              RandomAllocator, KDTreeGreedyAllocator
│   ├── coordination/
│   │   ├── random_walk.py       — RandomWalkCoordinator: per-agent random walk
│   │   ├── reservation_table.py — ReservationTable: per-step cell reservations
│   │   ├── priority_manager.py  — PriorityManager: base/dynamic agent priorities
│   │   └── pibt_coordinator.py  — PIBTCoordinator: Priority Inheritance with Backtracking
│   └── allocation/
│       ├── random_allocator.py         — RandomAllocator: random task/agent matching
│       └── kdtree_greedy_allocator.py  — KDTreeGreedyAllocator: design stub (NotImplementedError)
│
├── diagrammes/                  — PlantUML class diagram sources + generated PNGs
├── main.py                      — random-walk demo entry point
└── demo_pibt.py                 — interactive PIBT demo entry point
```

Dependency direction (strict, matches the class diagram): `mrta -> core` ; `algo -> core, mrta` ; `client -> core`.

---

## Classes in `core/`

### `Position` — `core/entities/position.py`
```python
@dataclass(frozen=True)
class Position:
    x: int
    y: int
    def __add__(self, other: Position) -> Position  # vector addition
```
Hashable (frozen). Used as a dict key in `Grid._agents` and `Grid._static`.

---

### `WorldEntity` — `core/entities/entity.py`
```python
class WorldEntity:
    entity_id:       int
    position:        Position
    appear_at:       int   # step at which the entity spawns (0 = immediate)
    blocks_movement: bool  # True -> cell impassable for agents
    scale:           int   # footprint size in cells (default 1)
    active:          bool  # property, True by default
```
Common base for any entity placed on the grid. Blocking obstacles are created with `WorldEntity(id, pos, blocks_movement=True)` — **no dedicated subclass needed**.

---

### `Agent` — `core/entities/agent.py`
```python
class Agent(WorldEntity):
    agent_id:    int        # alias of entity_id
    steps_taken: int
    blocks_movement = True  # (passed to super().__init__)
    def move_to(new_position: Position)   # updates position + steps_taken
    def __eq__ / __hash__                 # based on agent_id — hashable, usable as a dict key
```
`agent_id` is immutable -> stable hash. Used as a dict key in `PIBTCoordinator.goals` and internally in `PriorityManager`/`ReservationTable`.
Constructor: `Agent(agent_id, position)` — no strategy of its own, movement is always delegated to the `Coordinator`.

---

### `Grid` — `core/environment/grid.py`
```python
class Grid:
    width: int
    height: int
    _agents: dict[Position, Agent]
    _static: dict[Position, list[WorldEntity]]

    is_valid(position) -> bool
    is_blocked(position) -> bool        # True if an agent OR an active blocking entity occupies it
    place(entity: WorldEntity)          # raises if invalid; raises if an agent cell is already taken
    remove(entity: WorldEntity)
    get_agent_at(position) -> Agent | None
    get_entities_at(position, kind=None) -> list[WorldEntity]   # filters active=True on _static
    get_all(kind=None) -> list[WorldEntity]
```

---

### `PlanResult` — `core/engine/plan_result.py`
```python
@dataclass
class PlanResult:
    positions:   dict[int, Position]   # agent_id -> next Position (universal contract)
    moves:       dict[int, tuple]      # agent_id -> (from, to)     (universal contract)
    order:       list[int]             # agent_ids in priority order   (optional diagnostic)
    inheritance: list[tuple]           # (pusher_id, pushed_id)        (optional diagnostic)
    priorities:  dict[int, float]      # agent_id -> priority          (optional diagnostic)
```
DTO returned by every `Coordinator.plan()` call. `positions`/`moves` are the contract every coordinator fills; the rest are diagnostics, left empty outside the PIBT family. Keys are `agent_id` integers so it can cross the core -> client boundary without exposing `Agent` objects.

---

### `Coordinator` / `PriorityBasedCoordinator` — `core/engine/coordinator.py`
```python
class Coordinator(ABC):
    @abstractmethod
    def plan(self, agents: list[Agent], grid: Grid) -> PlanResult: ...
    def set_goal(self, agent: Agent, target: Position) -> None: ...  # no-op default

class PriorityBasedCoordinator(Coordinator):
    @abstractmethod
    def set_priority(self, agent: Agent, priority: float) -> None: ...
```
`Coordinator` is the interface for every MAPF algorithm; `set_goal` has a no-op default so goal-less coordinators (e.g. random walk) don't need to implement it. `PriorityBasedCoordinator` segregates `set_priority` for algorithms driven by priorities (interface segregation) — `FleetManager` depends on this narrower interface, `Simulation` only depends on `Coordinator`.

---

### `Dispatcher` — `core/engine/dispatcher.py`
```python
class Dispatcher(ABC):
    @abstractmethod
    def dispatch(self, agents: list[Agent], grid: Grid, step: int) -> None: ...
```
Pre-planning hook: `Simulation.step()` runs the dispatcher (if attached) **before** `coordinator.plan()`, so goals are never stale by construction. Living in `core` lets `Simulation` own the tick order (dispatch → plan) **without importing `mrta`** — the same dependency-inversion seam as `Coordinator`. `FleetManager` (in `mrta`) is the concrete dispatcher.

---

### `Simulation` — `core/engine/simulation.py`
```python
class Simulation:
    grid:         Grid
    agents:       list[Agent]
    entities:     list[WorldEntity]
    _pending:     list[WorldEntity]
    current_step: int
    coordinator:  Coordinator            # mandatory — no per-agent fallback
    dispatcher:   Dispatcher | None       # optional — run before planning each step

    __init__(grid, coordinator, dispatcher=None)
    add_agent(agent)         # place + append
    add_object(entity)       # append + place immediately if appear_at <= current_step
    step() -> PlanResult     # spawn -> dispatch -> plan -> move ; returns the PlanResult
```

**`step()` logic:**
```python
# 1. Spawn deferred entities whose appear_at step has been reached
# 2. Dispatch tasks (if a dispatcher is attached): self.dispatcher.dispatch(agents, grid, current_step)
# 3. Coordinated planning (mandatory): result = self.coordinator.plan(self.agents, self.grid)
# 4. Apply result.positions (lift agents, move, place back)
# 5. Return result — clients read diagnostics from it without importing algo
```
The `dispatch → plan` order is owned by `step()`, so a caller cannot plan on stale goals. Movement is applied by `step()` itself (lift-then-place: `grid.remove` → `agent.move_to` → `grid.place`) to handle simultaneous swaps — `agent.move_to` is never called outside this transaction, so `Agent.position` and the grid index stay in sync.

Note: `step()` returning the `PlanResult` is the one deliberate deviation from the class diagram (which shows `void`) — it's how renderers get PIBT diagnostics without depending on `algo`.

---

## Classes in `client/`

### `Renderer` — `client/renderer.py`
```python
class Renderer:
    sim: Simulation
    _caption: str = "Grid Simulation"   # override in subclasses
    def run(steps: int, pause: float = 1.0)
    def _draw(screen, font, font_sm, font_hdr, w, h)
```
Generic rendering: grid, agents (colored circles), static entities (squares). Constants `CELL=60`, `MARGIN=36`, `AGENT_COLORS`, `OBJ_COLORS` defined here and importable. Stores the last `PlanResult` from `sim.step()` in `self._last_result` for subclasses.

### `PIBTRenderer` — `client/pibt_renderer.py`
```python
class PIBTRenderer(Renderer):
    _caption = "PIBT Simulation"
    def _draw(...)   # overridden: adds goal cells (□) + agent priorities
```
Usage: `PIBTRenderer(sim).run(steps=30, pause=0.5)`. Read-only, forward playback. Reads goals from `sim.coordinator.goals` (duck-typed public attribute — no `algo` import) and priorities from `self._last_result.priorities`.

### `PIBTInteractiveRenderer` — `client/pibt_interactive_renderer.py`
```python
class PIBTInteractiveRenderer:
    sim: Simulation
    def run(steps: int = 30, auto_ms: int = 600)
    def run_debug(steps: int = 30)   # terminal print, no pygame

@dataclass
class StepSnapshot:
    step: int
    result: PlanResult     # the step's plan (positions + diagnostics)
    goals: dict
    objects: list
```
Usage: `PIBTInteractiveRenderer(sim).run(steps=80, auto_ms=500)`.

Keyboard: `Space` pause/play · `->` step forward · `<-` step back · `Q` quit.

The footer shows, for each step, the priority order, each agent's move, and any priority inheritances triggered — read from `snap.result` (a `PlanResult`), not from any `algo`-specific attribute.

---

## Classes in `algo/`

### `RandomWalkCoordinator` — `algo/coordination/random_walk.py`
```python
class RandomWalkCoordinator(Coordinator):
    def plan(agents, grid) -> PlanResult  # per-agent random walk
```
Minimal coordinator: each agent tries random directions until it finds a valid, unblocked, not-yet-claimed cell (falls back to staying in place).

---

### PIBT decomposition — `algo/coordination/`

PIBT is split across three classes: `PIBTCoordinator` holds the algorithm, while reservations and priorities each live in their own class (`ReservationTable`, `PriorityManager`). `PIBTCoordinator` implements `PriorityBasedCoordinator`. **Zero pygame dependency** — rendering lives in `client/`.

```python
class ReservationTable:            # algo/coordination/reservation_table.py
    _reserved: dict[Position, Agent]
    reserve(agent, pos)             # releases the agent's previous reservation first
    release(agent)                  # frees the agent's reservation (backtracking)
    get_reserving_agent(pos) -> Agent | None
    get_reservation(agent) -> Position | None
    clear()

class PriorityManager:             # algo/coordination/priority_manager.py
    _base: dict[Agent, float]      # priorities set explicitly (initial, inheritance, goal-reached)
    _dynamic: dict[Agent, float]   # effective priorities used to rank agents
    update(agents)                  # inits missing agents, then decays every dynamic priority by 1
    get_priority(agent) -> float
    set_base(agent, p)              # writes both _base and _dynamic immediately

class PIBTCoordinator(PriorityBasedCoordinator):   # algo/coordination/pibt_coordinator.py
    goals: dict[Agent, Position]     # public — read by PIBTRenderer/PIBTInteractiveRenderer
    _reservations: ReservationTable
    _priorities: PriorityManager
    _processed: set[Agent]
    _inheritance: list[tuple[Agent, Agent]]

    plan(agents, grid) -> PlanResult
    set_goal(agent, target)
    set_priority(agent, priority)
    _pibt(agent, parent, grid) -> bool     # grid passed as an argument, no stored grid state
    _h(pos, agent, grid) -> int            # Manhattan distance heuristic
```

**Usage** (no mandatory construction order — configure via `set_goal`/`set_priority`):
```python
a0 = Agent(0, Position(0, 0))
a1 = Agent(1, Position(9, 9))

pibt = PIBTCoordinator()
pibt.set_goal(a0, Position(9, 9))
pibt.set_goal(a1, Position(0, 0))
pibt.set_priority(a0, 5.0)   # optional — default is insertion order

sim = Simulation(grid, coordinator=pibt)
sim.add_agent(a0)
sim.add_agent(a1)

PIBTRenderer(sim).run(steps=30, pause=0.5)
```

**Internal mechanics:**
- Dynamic priorities decay by 1 every step -> prevents starvation.
- An agent at its goal gets base priority `-inf` (processed last, prefers to stay).
- Priority Inheritance: if agent i wants k's cell, `set_base(k, get_priority(i) + EPSILON)` then `_pibt(k, i, grid)` recurses.
- Backtracking: if k cannot move, i tries another candidate cell (`ReservationTable.release`).
- Obstacles are detected via `entity.blocks_movement and entity.active` on the grid's static entities.

**Adding a new Coordinator:**
```python
# in algo/coordination/my_algo.py
from core import Coordinator, PlanResult

class MyAlgo(Coordinator):
    def plan(self, agents, grid) -> PlanResult:
        positions = {a.agent_id: ... for a in agents}
        return PlanResult(positions=positions, moves={...})
```
Plug it in via `Simulation(grid, coordinator=MyAlgo())`. For a dedicated overlay, create `client/my_algo_renderer.py` extending `Renderer`.

---

## Classes in `mrta/`

`mrta` implements Multi-Robot Task Allocation on top of `core` only — it never imports `algo` or `client`.

```python
class TaskState(Enum):             # mrta/task.py
    PENDING, ASSIGNED, DONE

class Task:                        # mrta/task.py — hashable via task_id
    task_id: int
    target: Position
    priority: float
    state: TaskState
    assignee: Agent | None
    created_step: int

class TaskSource(ABC):             # mrta/task_source.py
    poll(current_step) -> list[Task]

class Allocator(ABC):              # mrta/allocator.py
    allocate(pending, free, grid) -> dict[Task, Agent]

class FleetManager(Dispatcher):    # mrta/fleet_manager.py — concrete Dispatcher
    source: TaskSource
    allocator: Allocator
    coordinator: PriorityBasedCoordinator

    dispatch(agents, grid, step)   # = _complete(agents) -> _intake(step) -> _allocate(agents, grid)
    set_priority(task_id, priority)
    _intake(step)                  # polls source, appends new tasks
    _allocate(agents, grid)        # matches pending tasks to free agents via allocator,
                                    # then pushes set_goal/set_priority to the coordinator
    _complete(agents)              # marks ASSIGNED tasks as DONE once assignee reaches target
```

The rendez-vous point between `mrta` and `algo` is the shared `PriorityBasedCoordinator` instance: `FleetManager` calls `set_goal`/`set_priority` on it, and `Simulation.step()` calls `plan()` on the very same object. Because `FleetManager` is a `Dispatcher`, `Simulation` owns the ordering: pass the fleet as `Simulation(grid, coordinator, dispatcher=fleet)` and `step()` runs `dispatch()` before `plan()` on every tick — the caller no longer sequences them by hand.

---

## Classes in `algo/allocation/`

```python
class RandomAllocator(Allocator):          # implemented — random pending/free matching
class KDTreeGreedyAllocator(Allocator):    # design stub — raises NotImplementedError
    _tree   # placeholder for a KD-tree spatial index (e.g. scipy.spatial.KDTree)
    _nearest_free(task, free) -> Agent      # also a stub
```
`KDTreeGreedyAllocator` is intentionally unimplemented: the indexing strategy (rebuild cost per dispatch cycle, tie-breaking, distance metric on a discrete grid) needs discussion before implementation.

---

## Strict rules

- **`core/` must never import `client/`, `algo/`, or `mrta/`** — strictly one-directional dependency.
- **`mrta/` must never import `algo/` or `client/`** — it depends only on `core`.
- **`algo/` must never import `client/`** — algorithms are pure, no rendering.
- **Visual/rendering changes -> `client/` only.**
- **Keep the diagram in sync**: after adding a class or attribute, update `diagrammes/diag_commente.puml` and regenerate with `plantuml diagrammes/diag_commente.puml`.

---

## Key design constraints

| Constraint | Detail |
|---|---|
| One agent per cell | `Grid.place()` raises, `Grid.move()` returns False |
| `Position` is immutable | frozen dataclass, never mutated |
| `Agent` is hashable | via `agent_id`, usable as a dict key |
| Deferred spawn | `appear_at > 0` -> held in `_pending` until the right step |
| Coordinator is mandatory | `Simulation` refuses to run without one |
| Obstacle = WorldEntity | `WorldEntity(id, pos, blocks_movement=True)` suffices — no subclass |
| Goal stability | PIBT inserts `loc(i)` first among candidates if `loc(i) == goal(i)` |
| Algorithms have no rendering | `algo/` never imports pygame — all rendering goes through `client/` |
| `PlanResult` is the universal contract | every `Coordinator.plan()` returns one; diagnostics are optional |
| Interface segregation | `set_priority` lives on `PriorityBasedCoordinator`, not `Coordinator` |
