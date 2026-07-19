# AGENT.md

> **This is the project map for coding agents. Everything needed to work on this repo is here.**
> **Do not re-explore the tree to answer structural questions — read this file first.**

---

## Running the simulation

```bash
python main.py                                  # 15x15, 20 agents, PIBT + MRTA, interactive window
python main.py --tasks random                   # same, self-generating background work
python main.py --algo random --mode static      # the historical random-walk demo
python demo_pibt.py                             # legacy PIBT demo (5x5, keyboard navigation)
python demo_pibt.py -d                          # same, debug mode: terminal print, zero pygame
python sim_many_pibt.py --seeds 2               # headless L0 benchmark sweep -> sim_results.csv
python sim_many_mrta.py --seeds 2               # MRTA post-run report -> mrta_results.csv
python sim_many_mrta.py --obstacles 14 --per-task mrta_tasks.csv   # + failure paths, per-task drill-down
```

**Two reports, two questions.** `sim_many_pibt.py` asks "does PIBT route agents to fixed
goals" — but its `success_rate` **latches on the first time an agent touches its goal** and is
never invalidated (`sim_many_pibt.py:87`), so a fleet that converges then scatters still scores
100%. `sim_many_mrta.py` reports the task lifecycle instead, with every distribution given as
**mean and max** because the failure mode is "nineteen agents are fine and one is not" — the
exact thing a mean hides. Key columns: `drift_max` / `drift_agents` (agents pushed off a
completed target), `goalless_frac`, `reassignments`, `failed_unreachable` vs `failed_stalled`,
and `dispatch_ms_mean` vs `plan_ms_mean` (allocator cost separated from planner cost).

`main.py` flags: `--width/--height` (15), `--agents` (20), `--obstacles`, `--algo {pibt,random}`,
`--mode {mrta,static}`, `--tasks {none,random}`, `--frontend {pygame,headless}`, `--steps`,
`--seed`, `--tick-ms`.

**In the window**: click an agent to toggle it, drag a rubber band to select several, then click a
cell to send the batch there. `Space` play/pause · `→` step · `←` replay backwards · `A`/`C`
select all / clear · `Q` quit.

Dependencies: `requirements.txt` + pygame (`pip install pygame`).

**Fastest ways to exercise the code without a window** (use these to verify changes):
```bash
python main.py --frontend headless --tasks random --steps 20   # full MRTA path
python main.py --frontend headless --mode static --algo random --steps 10
python demo_pibt.py -d
python sim_many_pibt.py --seeds 2                              # ~200 instances, a few seconds
```
There is currently **no test suite** — these are the de-facto regression checks.

---

## Layout

```
.
├── core/                       — pure engine, zero rendering dependency
│   ├── __init__.py             — re-exports: Position, WorldEntity, Agent, Grid, Simulation,
│   │                             Coordinator, PlanResult, DispatchIntent, Dispatcher, StaticDispatcher
│   ├── entities/
│   │   ├── position.py         — Position (frozen dataclass, hashable, +)
│   │   ├── entity.py           — WorldEntity (base, blocks_movement, appear_at, scale)
│   │   └── agent.py            — Agent (hashable via agent_id, blocks_movement=True)
│   ├── environment/
│   │   └── grid.py             — Grid (spatial source of truth)
│   └── engine/
│       ├── plan_result.py      — PlanResult (DTO returned by Coordinator.plan())
│       ├── dispatch_intent.py  — DispatchIntent (DTO of goals/priorities, consumed by plan())
│       ├── coordinator.py      — Coordinator (ABC: plan(agents, grid, intent))
│       ├── dispatcher.py       — Dispatcher (ABC: dispatch() -> DispatchIntent, run by Simulation.step)
│       ├── static_dispatcher.py — StaticDispatcher (fixed intent every tick; MRTA-free scenarios)
│       └── simulation.py       — Simulation (engine, coordinator mandatory, dispatcher optional)
│
├── client/                     — presentation: scripting API, frozen views, frontends
│   ├── __init__.py             — lazy (PEP 562) re-exports of the legacy pygame renderers
│   ├── control/                — PART 1: scripting API, pygame-free (COMPOSITION ROOT)
│   │   ├── config.py           — ScenarioConfig (frozen)
│   │   ├── factory.py          — build(config) -> SimulationController
│   │   └── controller.py       — SimulationController: step / run / send_batch_to / snapshot
│   ├── view/                   — frozen value types shared by control and frontends
│   │   ├── task_view.py        — TaskView (frozen projection of a Task, assignee_id: int)
│   │   └── snapshot.py         — StepSnapshot (result, goals, objects, tasks, counters)
│   ├── frontends/              — PART 2: presentation only
│   │   ├── frontend.py         — Frontend (ABC: run(steps))
│   │   ├── pygame_frontend.py  — interactive window: board + selection + batch dispatch
│   │   ├── sidebar.py          — Sidebar: selection readout, task tallies, buttons
│   │   └── headless_frontend.py — terminal output, zero pygame
│   ├── renderer.py             — LEGACY Renderer (generic pygame loop) — demo_pibt.py only
│   ├── pibt_renderer.py        — LEGACY PIBTRenderer
│   └── pibt_interactive_renderer.py — LEGACY PIBTInteractiveRenderer (pre-computed history)
│
├── mrta/                        — Multi-Robot Task Allocation, depends only on core
│   ├── __init__.py              — re-exports: Task, TaskState, TaskSource, QueueTaskSource,
│   │                              RandomTaskSource, ScriptedTaskSource, CompositeTaskSource,
│   │                              Allocator, FleetManager
│   ├── task.py                  — TaskState (enum, incl. FAILED), Task (dataclass)
│   ├── task_source.py           — TaskSource (ABC: poll(current_step) -> list[Task])
│   ├── queue_task_source.py     — QueueTaskSource: externally fed queue, drained per poll
│   ├── random_task_source.py    — RandomTaskSource: seeded random tasks on free cells
│   ├── scripted_task_source.py  — ScriptedTaskSource: {step: [Task]} schedule
│   ├── composite_task_source.py — CompositeTaskSource: merges several sources
│   ├── allocator.py             — Allocator (ABC: allocate(pending, free, grid) -> dict[Task, Agent])
│   └── fleet_manager.py         — FleetManager (complete -> watchdog -> prune -> intake -> allocate)
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
├── rapport_plan.md              — design report on the task lifecycle (French, working doc)
├── main.py                      — CLI entry point (argparse -> client.control.build)
└── demo_pibt.py                 — legacy interactive PIBT demo entry point
```

**Dependency direction** (strict, matches the class diagram):

```
mrta            -> core
algo            -> core, mrta
client.view     -> core, mrta (VALUE types only: Position, TaskState)
client.control  -> core, algo, mrta            (composition root)
client.frontends-> core, client.view           (read-only)
```

`client/` can no longer "depend only on core": picking the algorithm and wiring the fleet *is*
the scripting API's job. The rule that replaces it: **frontends know neither `algo` nor any mrta
*behaviour*** (`FleetManager`, `Allocator`, `TaskSource`) — they see frozen values only.
`TaskView.state` importing `TaskState` is a dependency on a *value*, not on behaviour;
duplicating the enum client-side would reintroduce drift, typing it `str` would lose the safety.

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

### `DispatchIntent` — `core/engine/dispatch_intent.py`
```python
@dataclass(frozen=True)
class DispatchIntent:
    goals:      dict[int, Position]   # agent_id -> target (absolute, this tick)
    priorities: dict[int, float]      # agent_id -> allocation priority (optional per agent)
```
Immutable, `agent_id`-keyed carrier of the **absolute** allocation state for one tick (complete state, not deltas). Produced by a `Dispatcher`, consumed by `Coordinator.plan()`. It is the *only* channel for goals/priorities — there is no external mutation of the coordinator, which keeps allocation (`mrta`) and navigation (`algo`) decoupled and gives an auditable per-tick record.

---

### `Coordinator` — `core/engine/coordinator.py`
```python
class Coordinator(ABC):
    @abstractmethod
    def plan(self, agents: list[Agent], grid: Grid, intent: DispatchIntent) -> PlanResult: ...
```
The single-method interface for every MAPF algorithm. Goals and priorities arrive only through `intent`; a priority-less coordinator (e.g. random walk) simply ignores `intent.priorities`. Any `Coordinator` can therefore be paired with any `Dispatcher`.

---

### `Dispatcher` / `StaticDispatcher` — `core/engine/dispatcher.py`, `static_dispatcher.py`
```python
class Dispatcher(ABC):
    @abstractmethod
    def dispatch(self, agents: list[Agent], grid: Grid, step: int) -> DispatchIntent: ...

class StaticDispatcher(Dispatcher):
    def __init__(self, goals: dict[int, Position], priorities: dict[int, float] | None = None): ...
    def dispatch(self, agents, grid, step) -> DispatchIntent   # same fixed intent every tick
```
Pre-planning hook: `Simulation.step()` runs the dispatcher (if attached) **before** `plan()` and passes the returned intent to it, so goals are never stale by construction. It never touches the coordinator. Living in `core` lets `Simulation` own the tick order (dispatch → plan) **without importing `mrta`** — the same dependency-inversion seam as `Coordinator`. `FleetManager` (`mrta`) and `StaticDispatcher` are the concrete dispatchers; use `StaticDispatcher` for fixed-goal scenarios that need no task allocation.

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
    dispatcher:   Dispatcher | None       # optional — produces this tick's intent
    last_intent:  DispatchIntent          # the intent used by the last step (auditable)

    __init__(grid, coordinator, dispatcher=None)
    add_agent(agent)         # place + append
    add_object(entity)       # append + place immediately if appear_at <= current_step
    step() -> PlanResult     # spawn -> dispatch -> plan -> move ; returns the PlanResult
```

**`step()` logic:**
```python
# 1. Spawn deferred entities whose appear_at step has been reached
# 2. Dispatch: intent = self.dispatcher.dispatch(...) if dispatcher else DispatchIntent()  (empty)
# 3. Coordinated planning (mandatory): result = self.coordinator.plan(self.agents, self.grid, intent)
# 4. Apply result.positions (lift agents, move, place back)
# 5. Return result — clients read diagnostics from it without importing algo
```
The `dispatch → plan` order is owned by `step()`, so a caller cannot plan on stale goals. Movement is applied by `step()` itself (lift-then-place: `grid.remove` → `agent.move_to` → `grid.place`) to handle simultaneous swaps — `agent.move_to` is never called outside this transaction, so `Agent.position` and the grid index stay in sync.

Note: `step()` returning the `PlanResult` is the one deliberate deviation from the class diagram (which shows `void`) — it's how renderers get PIBT diagnostics without depending on `algo`.

---

## Classes in `client/`

### `ScenarioConfig` — `client/control/config.py`
```python
@dataclass(frozen=True)
class ScenarioConfig:
    width: int = 15;  height: int = 15;  agents: int = 20;  obstacles: int = 0
    algo: str = "pibt"    # "pibt" | "random"
    mode: str = "mrta"    # "mrta" | "static"
    seed: int = 0
    tasks: str = "none"   # "none" | "random"  — background generation
    task_every: int = 5;  task_count: int = 2
    patience: int = 12;   max_attempts: int = 3    # FleetManager watchdog tuning
```
Frozen: a config is a record of what was asked for, so a run is reproducible from it plus its
seed. `__post_init__` rejects unknown algo/mode/tasks and a scenario that cannot fit.

### `build` — `client/control/factory.py`
```python
def build(config: ScenarioConfig) -> SimulationController
```
**The composition root** — the one place allowed to know `algo` and `mrta` concretely. Draws
collision-free starts with `random.Random(seed)`, picks the coordinator, and in MRTA mode always
attaches a `QueueTaskSource` (so `send_batch_to` works), composing a `RandomTaskSource` alongside
it when `tasks="random"`. Swapping in a new algorithm or allocator touches this file only.

### `SimulationController` — `client/control/controller.py`
```python
class SimulationController:
    sim: Simulation
    fleet: FleetManager | None      # MRTA mode only
    queue: QueueTaskSource | None   # MRTA mode only

    step() -> StepSnapshot                    # pure "advance by one" — owns no clock
    run(steps) -> list[StepSnapshot]
    send_batch_to(target, agent_ids=None, priority=5.0) -> list[Task]
    snapshot() -> StepSnapshot
```
The single seam between a built scenario and whatever drives it. `send_batch_to` mints one task
per destination cell — `target` first, then outwards by BFS over free cells — with
`eligible=frozenset(agent_ids)`, and pushes them into the queue.

**"Send this batch to B" *is* an allocation problem**: nothing bypasses the planner, so a batch
move inherits collision avoidance for free. That is why there is no manual per-cell driving
anywhere in this API. The BFS follows connectivity rather than scanning a radius, so it never
returns a cell that looks near but sits behind a wall.

### `TaskView` / `StepSnapshot` — `client/view/`
```python
@dataclass(frozen=True)
class TaskView:
    task_id: int;  target: Position;  state: TaskState
    priority: float;  assignee_id: int | None;  attempts: int
    @classmethod
    def of(task: Task) -> TaskView       # copies VALUES — never holds the Task or its assignee

@dataclass(frozen=True)
class StepSnapshot:
    step: int
    result: PlanResult
    goals: dict[int, Position]           # from sim.last_intent, not from the coordinator
    objects: tuple                       # ((Position, kind), ...)
    tasks: tuple[TaskView, ...]
    completed: int;  failed: int
    def counts() -> dict[str, int]       # pending/assigned live + done/failed cumulative
```
**Why a projection and not the `Task`**: a `Task` is mutable and owned by `FleetManager`, which
keeps mutating it (ASSIGNED → DONE) then prunes it. Archiving the task itself would let a stored
frame rewrite its own past, and a live `task.assignee.position` would contradict the frozen
`result.positions[id]` *inside the same snapshot*. Reducing the assignee to its `agent_id` is
the rule `PlanResult` already applies. This is precisely what makes it sound for a frontend to
keep a history while the engine runs on.

### `Frontend` / `HeadlessFrontend` / `PygameFrontend` — `client/frontends/`
```python
class Frontend(ABC):
    controller: SimulationController
    def run(steps: int)

class HeadlessFrontend(Frontend):   # terminal, zero pygame
class PygameFrontend(Frontend):     # PygameFrontend(controller, tick_ms=350)
```
`PygameFrontend` holds one board-drawing routine (the three legacy renderers each carried a
near-identical copy), with **`CELL` derived** from grid size and a window budget instead of the
old hard-coded 60.

Mouse: click an agent to toggle · drag a rubber band to select · click a cell to dispatch the
batch. Keys: `Space` play/pause · `→` step · `←` replay back · `A`/`C` select all / clear · `Q`.

- **Fixed-step accumulator**: the frontend owns the clock, so `step()` stays a pure "advance by
  one". `MAX_STEPS_PER_FRAME` is **not optional** — once a tick costs more than `tick_duration`
  the backlog grows without bound and the window freezes (spiral of death). The clamp degrades
  to slow motion instead.
- **Backward navigation is replay only.** `Grid` and `PriorityManager` are destructive, so the
  engine has no undo: frozen snapshots make *looking* back safe, not *rewinding*. A deliberate
  regression against `PIBTInteractiveRenderer`, whose symmetry needs a pre-computed history and
  is therefore incompatible with interactivity.
- **No threads**: `Grid`/`Agent` are mutated while read, and PIBT is CPU-bound so the GIL
  cancels the gain. Concurrency buys nothing and costs correctness.

---

## Legacy renderers in `client/` (used by `demo_pibt.py` only)

Kept as the pre-existing regression path. New work goes through `client/frontends/`.
They are re-exported lazily from `client/__init__.py` (PEP 562) so importing `client.control`
or `client.view` never pulls pygame in.

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
    def plan(agents, grid, intent) -> PlanResult  # per-agent random walk; ignores intent
```
Minimal coordinator: each agent tries random directions until it finds a valid, unblocked, not-yet-claimed cell (falls back to staying in place).

---

### PIBT decomposition — `algo/coordination/`

PIBT is split across three classes: `PIBTCoordinator` holds the algorithm, while reservations and priorities each live in their own class (`ReservationTable`, `PriorityManager`). `PIBTCoordinator` implements `Coordinator`. **Zero pygame dependency** — rendering lives in `client/`.

```python
class ReservationTable:            # algo/coordination/reservation_table.py
    _reserved: dict[Position, Agent]
    reserve(agent, pos)             # releases the agent's previous reservation first
    release(agent)                  # frees the agent's reservation (backtracking)
    get_reserving_agent(pos) -> Agent | None
    get_reservation(agent) -> Position | None
    clear()

class PriorityManager:             # algo/coordination/priority_manager.py
    _base: dict[Agent, float]      # priorities set explicitly (intent re-seed, inheritance, goal-reached)
    _dynamic: dict[Agent, float]   # effective priorities used to rank agents
    update(agents)                  # inits missing agents, then decays every dynamic priority by 1
    get_priority(agent) -> float
    set_base(agent, p)              # writes both _base and _dynamic immediately

class PIBTCoordinator(Coordinator):   # algo/coordination/pibt_coordinator.py
    goals: dict[Agent, Position]     # public — rebuilt each tick from the intent; read by renderers
    _reservations: ReservationTable
    _priorities: PriorityManager
    _processed: set[Agent]
    _inheritance: list[tuple[Agent, Agent]]
    _last_intent: dict[int, tuple]   # last (goal, priority) per agent — for the re-seed guard

    plan(agents, grid, intent) -> PlanResult
    _apply_intent(agents, intent)          # rebuild goals; re-seed base priority only on change
    _pibt(agent, parent, grid) -> bool     # grid passed as an argument, no stored grid state
    _h(pos, agent, grid) -> int            # Manhattan distance heuristic
```

**Usage** — goals/priorities come from the intent, via a dispatcher:
```python
a0 = Agent(0, Position(0, 0))
a1 = Agent(1, Position(9, 9))

pibt = PIBTCoordinator()
dispatcher = StaticDispatcher(
    goals={0: Position(9, 9), 1: Position(0, 0)},
    priorities={0: 5.0, 1: 3.0},          # optional
)
sim = Simulation(grid, coordinator=pibt, dispatcher=dispatcher)
sim.add_agent(a0)
sim.add_agent(a1)

PIBTRenderer(sim).run(steps=30, pause=0.5)
```

**Internal mechanics:**
- Goals are rebuilt each tick from `intent.goals` (an agent with no goal stays in place).
- **Re-seed guard**: the base priority is re-seeded from `intent.priorities` **only** when an agent's goal or business priority changed since last tick — otherwise the dynamic priority drift (anti-starvation) would be wiped. This is the crux of keeping the coordinator stateless about allocation while stateful about navigation.
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
    def plan(self, agents, grid, intent) -> PlanResult:
        positions = {a.agent_id: intent.goals.get(a.agent_id, a.position) for a in agents}
        return PlanResult(positions=positions, moves={...})
```
Plug it in with a dispatcher that supplies the goals, e.g. `Simulation(grid, coordinator=MyAlgo(), dispatcher=StaticDispatcher(goals={...}))`. For a dedicated overlay, create `client/my_algo_renderer.py` extending `Renderer`.

---

## Classes in `mrta/`

`mrta` implements Multi-Robot Task Allocation on top of `core` only — it never imports `algo` or `client`.

```python
class TaskState(Enum):             # mrta/task.py
    PENDING, ASSIGNED, DONE, FAILED

class Task:                        # mrta/task.py — hashable via task_id
    task_id: int                   # stamped by FleetManager at intake, not by the source
    target: Position
    priority: float
    state: TaskState
    assignee: Agent | None
    created_step: int
    eligible: frozenset[int] | None    # agent_ids allowed to take it (None = anyone)
    attempts: int                      # assignees burned through so far
    best_distance: int | None          # best Manhattan distance ever reached
    last_improvement_step: int         # step at which best_distance last improved

class TaskSource(ABC):             # mrta/task_source.py
    poll(current_step) -> list[Task]

class QueueTaskSource(TaskSource):    # push / push_many, poll() drains and empties
class RandomTaskSource(TaskSource):   # (grid, every, count, seed)
class ScriptedTaskSource(TaskSource): # ({step: [Task]})
class CompositeTaskSource(TaskSource):# (*sources) — polled in order, concatenated

class Allocator(ABC):              # mrta/allocator.py
    allocate(pending, free, grid) -> dict[Task, Agent]

class FleetManager(Dispatcher):    # mrta/fleet_manager.py — concrete Dispatcher
    source: TaskSource
    allocator: Allocator
    patience: int                  # steps without progress before releasing an assignee
    max_attempts: int              # assignees a task may burn before it is FAILED
    tasks: list[Task]
    completed_count: int
    failed_count: int

    dispatch(agents, grid, step) -> DispatchIntent
    #   _complete -> _watchdog -> _prune -> _intake -> _allocate -> _build_intent
    set_priority(task_id, priority)
    _complete(agents)              # ASSIGNED -> DONE once the assignee stands on the target
    _watchdog(step)                # releases stalled assignees; FAILED past max_attempts
    _prune()                       # drops terminal tasks, counting them on the way out
    _intake(step, grid)            # stamps ids; FAILED at once if the target is unreachable
    _allocate(agents, grid)        # one allocator call per eligibility class, restricted first
    _build_intent() -> DispatchIntent  # goals/priorities of the ASSIGNED tasks
```

**Task lifecycle** — `PENDING -> ASSIGNED -> DONE` is nominal; `FAILED` is terminal for
abandoned work. Two guards close the allocation deadlock a plain three-state lifecycle left open
(an unreachable target consumed its assignee *forever*, since `_allocate` excludes ASSIGNED
agents from the free pool — a fleet silently losing robots while looking healthy):

- **static, at intake** — a target off the grid or under a blocking entity is rejected outright;
- **dynamic, the watchdog** — an assignee that has not improved its Manhattan distance to the
  target for `patience` steps is released and the task retried; past `max_attempts` distinct
  assignees, the *target* is blamed and the task FAILED.

We deliberately do **not** try to *prove* a target reachable: reachability is not static in a
world with `appear_at`, and proving it would duplicate the planner with a rival notion of
"reachable". We observe the absence of progress instead. Terminal tasks are pruned but
**counted** — dropping work silently would hide the very deadlock this closes.

The watchdog belongs to `FleetManager` because it is the only component seeing a task *across*
ticks; in the coordinator it would re-couple navigation with allocation semantics, exactly what
`DispatchIntent` separated. Full rationale in `rapport_plan.md`.

**Eligibility** — `Task.eligible` restricts who may take a task, so a caller can send a
*specific* batch somewhere. `_allocate()` groups pending tasks by eligibility class and calls
the allocator once per class, **restricted classes first** (otherwise an unrestricted task could
steal a reserved agent), removing matched agents from the pool between calls. The constraint
lives on the *request*, not on the matching *strategy*, so the `Allocator` interface is
untouched and new allocators need no adaptation.

`FleetManager` holds **no coordinator reference**: it is pure w.r.t. the engine. It returns a `DispatchIntent`, and `Simulation.step()` passes it to `plan()`. `Simulation` owns the ordering: `Simulation(grid, coordinator, dispatcher=fleet)` and `step()` runs `dispatch()` before `plan()` every tick — the caller no longer sequences them by hand.

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
- **`client/frontends/` must never import `algo/`, nor mrta *behaviour*** (`FleetManager`,
  `Allocator`, `TaskSource`) — only `core` and the frozen types in `client/view/`. Value types
  (`Position`, `TaskState`) are fine. Composition belongs in `client/control/`.
- **Visual/rendering changes -> `client/frontends/` only.**
- **Never call `SimulationController.step()` in a loop with a sleep** — a frontend owns the
  clock, and any real-time loop needs the `MAX_STEPS_PER_FRAME` clamp.
- **Keep the diagrams in sync**: after adding a class or attribute, update `diagrammes/_model.iuml` (the single class-diagram source) and `diagrammes/sequence_tick.puml` (one-tick sequence), and regenerate with `plantuml diagrammes/diagrams.puml diagrammes/sequence_tick.puml`.
  `diagrams.puml` renders `_model.iuml` twice — simple and annotated — driven by the `$ANNOTATED`
  preprocessor flag, so the two class diagrams cannot drift apart. Never edit the generated PNGs.

---

## Key design constraints

| Constraint | Detail |
|---|---|
| One agent per cell | `Grid.place()` raises; `Simulation.step()` lifts all movers before placing them |
| `Position` is immutable | frozen dataclass, never mutated |
| `Agent` is hashable | via `agent_id`, usable as a dict key |
| Deferred spawn | `appear_at > 0` -> held in `_pending` until the right step |
| Coordinator is mandatory | `Simulation` refuses to run without one; a dispatcher is optional |
| Obstacle = WorldEntity | `WorldEntity(id, pos, blocks_movement=True)` suffices — no subclass |
| Goal stability | PIBT inserts `loc(i)` first among candidates if `loc(i) == goal(i)` |
| Algorithms have no rendering | `algo/` never imports pygame — all rendering goes through `client/` |
| `PlanResult` is the universal contract | every `Coordinator.plan()` returns one; diagnostics are optional |
| `DispatchIntent` decouples allocation from navigation | goals/priorities flow only through the intent; no external mutation of the coordinator, so any Coordinator pairs with any Dispatcher |
| Single mover | only `Simulation.step()` moves agents (lift→`move_to`→place); `agent.move_to` alone must not be called |
| Plans are validated, not rolled back | `Simulation._validate()` rejects an inapplicable `PlanResult` **before** any mutation, so the lift/place transaction cannot fail partially |
| Task identity belongs to the registry | `FleetManager` stamps `task_id` at intake; sources propose tasks without one, so several sources cannot collide (`Task` hashes on `task_id`) |
| `-inf` demotion is reversible | "at its goal" is a *state*; `PIBTCoordinator` saves the overwritten base and restores it as soon as the state stops holding |
| Snapshots are projections | `TaskView`/`StepSnapshot` copy values and key on `agent_id`; a snapshot must read identically N steps later |
| No unreachable task consumes an agent | intake guard + progress watchdog release the assignee and end in `FAILED`, **counted** not dropped |

