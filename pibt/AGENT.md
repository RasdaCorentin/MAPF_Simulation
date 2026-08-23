# pibt/ — Priority Inheritance with Backtracking

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`pibt/` is a concrete `PathPlanner` (Okumura et al., 2022). It imports only from `core` and is
`core/`'s only dependent right now (`mrta/`, which followed the same one-directional dependency,
was removed — see `TODO.md`). Restored from the pre-`algo/`-removal implementation (see `TODO.md`
at the repo root for that history) and re-parameterized onto the current `core` API
(`Coordinates2D`, `Grid2D`, `PathPlanner`, `StepOutcome`, `AssignmentManifest`) — the algorithm
itself is untouched.

### `ReservationTable` — `pibt/reservation_table.py`
Tracks which agent has reserved which `Coordinates2D` for the next step during one planning
pass. `reserve()` releases any prior reservation by the same agent first — one cell at a time.

### `PriorityManager` — `pibt/priority_manager.py`
Tracks each agent's base and effective (dynamic) priority. `update()` decays every dynamic
priority by 1 each tick (anti-starvation drift); `set_base()` preserves that accumulated drift
across a base-priority overwrite (goal-reached demotion, priority inheritance) rather than
flattening it.

### `pibt_core.run_pibt_pass()` — `pibt/pibt_core.py`
The recursive core (Algorithm 1), extracted so a caller other than `PIBTPlanner` can drive it
against an externally-owned `ReservationTable`/`PriorityManager` — e.g. a future LaCAM low
level that needs to pre-seed one agent's reservation and let the rest cascade around it. Does
not clear `reservations` itself: the caller decides what is already reserved before the pass.

⚠ **`_h()` is a raw Manhattan-distance heuristic, not obstacle-aware.** A single-cell obstacle
sitting exactly on a corridor can put two detour directions at equal heuristic distance; the
fixed `DIRS` tie-break can then oscillate an agent between two cells forever instead of
committing to one detour. See the note in `demo_one_shot.py`.

### `PIBTPlanner` — `pibt/pibt_planner.py`
Implements `PathPlanner.plan()`. Goals and base priorities are read from the tick's
`AssignmentManifest` — never set by external mutation. `AssignmentManifest.goals` is a
`list[Objective]` (each already `attach_to()`'d to the one Agent it is for, since 4e0c51f);
`_apply_intent()` flattens that to `agent_id -> Coordinates2D` once per tick before the rest of
the planner (unchanged since before `Objective` existed) reads it. Stateless about allocation,
but keeps its own navigation state across ticks (dynamic priority drift, reservations). An agent
parked on its goal is demoted to base priority `-inf` so it stops contesting cells it does not
need; `GoalReachedPolicy` (constructor argument) decides whether that demotion is undone once
the agent leaves its goal:
- `TRANSIENT` (default) — undone as soon as the agent leaves its goal. Mandatory under a
  rotating-goal regime (`TaskDrivenOrchestrator`) — an agent that just finished a mission must
  be able to contest a cell again.
- `PERMANENT` — never undone. Measurably better under a *static* goal regime
  (`OneShotGoalDispatcher`) — see the docstring on `GoalReachedPolicy` for the numbers.

⚠ **`orientation=True` (constructor argument, default `False`) is cosmetic, not LoRR-semantic.**
When on, `plan()` also fills `StepOutcome.orientations`: one heading per *moving* agent, derived
from `(next - current)` via `pibt_core.ORIENTATION_BY_DELTA` — an agent that stays in place is
simply absent, same convention as `positions`. It does not feed back into candidate selection
(the heuristic and candidate ranking are unchanged), costs nothing, and does not enforce a
rotate-XOR-move constraint — an agent can move and face its new direction in the same tick,
unlike League-of-Robot-Runners semantics (`core/AGENT.md`'s note on `Agent` covers what a real
rotate-XOR-move model would need, in both `core` and here). `ORIENTATION_BY_DELTA` also
establishes, for lack of one elsewhere in the repo, the x/y <-> compass convention this planner
uses: x increases East, y increases South.

### `OneShotGoalDispatcher` — `pibt/one_shot_dispatcher.py`
Minimal `MissionOrchestrator` local to this package, not a `core` class: `core`'s own
`FixedGoalDispatcher` was dropped in 4e0c51f rather than adapted, because it built its
`Objective`s at construction time, before any `Agent` existed to `attach_to()`. This one builds
them lazily inside `assign_missions()` instead, where the agents are available — one `Objective`
per agent with a configured goal, same fixed goal every tick. Just enough to drive the demo
below; not meant as a general-purpose replacement.

### `demo_one_shot.py`
First working end-to-end run: `python -m pibt.demo_one_shot`. Wires
`WorldEngine(grid, PIBTPlanner(), OneShotGoalDispatcher(goals))` — the mission side is one-shot
fixed goals, not `mrta` — and steps the engine until every agent reaches its goal or `MAX_STEPS`
is hit. Three agents cross through the grid's center, so priority inheritance is exercised, not
just three independent straight lines.
