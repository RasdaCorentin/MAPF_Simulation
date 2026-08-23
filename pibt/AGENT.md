# pibt/ — Priority Inheritance with Backtracking

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`pibt/` is a concrete `PathPlanner` (Okumura et al., 2022). It imports only from `core` —
never from `mrta` — the same one-directional dependency `mrta` itself follows. Restored from
the pre-`algo/`-removal implementation (see `TODO.md` at the repo root for that history) and
re-parameterized onto the current `core` API (`Coordinates2D`, `Grid2D`, `PathPlanner`,
`StepOutcome`, `AssignmentManifest`) — the algorithm itself is untouched.

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
`AssignmentManifest` — never set by external mutation. Stateless about allocation, but keeps
its own navigation state across ticks (dynamic priority drift, reservations). An agent parked
on its goal is demoted to base priority `-inf` so it stops contesting cells it does not need;
`GoalReachedPolicy` (constructor argument) decides whether that demotion is undone once the
agent leaves its goal:
- `TRANSIENT` (default) — undone as soon as the agent leaves its goal. Mandatory under a
  rotating-goal regime (`TaskDrivenOrchestrator`) — an agent that just finished a mission must
  be able to contest a cell again.
- `PERMANENT` — never undone. Measurably better under a *static* goal regime
  (`FixedGoalDispatcher`) — see the docstring on `GoalReachedPolicy` for the numbers.

### `demo_one_shot.py`
First working end-to-end run: `python -m pibt.demo_one_shot`. Wires
`WorldEngine(grid, PIBTPlanner(), FixedGoalDispatcher(goals))` — the mission side is
one-shot fixed goals, not `mrta` — and steps the engine until every agent reaches its goal or
`MAX_STEPS` is hit. Three agents cross through the grid's center, so priority inheritance is
exercised, not just three independent straight lines.
