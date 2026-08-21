# algo/ — MAPF algorithms

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`algo/` decides *how they move* (coordination) and, given a filtered set of candidates, *who
takes which job* (allocation). It depends on `core` and on `mrta`'s `Allocator`/`Task` —
**algorithms are pure computation**, no rendering, no I/O.

### `RandomWalkCoordinator` — `algo/coordination/random_walk.py`
```python
class RandomWalkCoordinator(Coordinator):
    def plan(agents, grid, intent) -> PlanResult  # per-agent random walk; ignores intent
```
Minimal coordinator: each agent tries random directions until it finds a valid, unblocked, not-yet-claimed cell (falls back to staying in place).

---

### PIBT decomposition — `algo/coordination/`

PIBT is split across four pieces: reservations and priorities each live in their own class
(`ReservationTable`, `PriorityManager`); the recursive core (Algorithm 1) is a free function,
`pibt_core.run_pibt_pass`, shared with `LaCAMCoordinator`'s low level (see the static-mode
section below) — a caller other than `PIBTCoordinator` can pre-seed a fixed reservation
before a pass and have it survive, which `PIBTCoordinator`'s own per-tick reset would
otherwise wipe. `PIBTCoordinator` itself is a thin per-tick wrapper: goal/priority
bookkeeping around one unconstrained call into the shared core.

```python
class ReservationTable:            # algo/coordination/reservation_table.py
    _reserved: dict[Position, Agent]
    reserve(agent, pos)             # releases the agent's previous reservation first
    release(agent)                  # frees the agent's reservation (backtracking)
    get_reserving_agent(pos) -> Agent | None
    get_reservation(agent) -> Position | None
    clear()

class PriorityManager:             # algo/coordination/priority_manager.py
    __init__(initial_priorities: dict[Agent, float] | None = None)
    _base: dict[Agent, float]      # priorities set explicitly (intent re-seed, inheritance, goal-reached)
    _dynamic: dict[Agent, float]   # effective priorities used to rank agents
    update(agents)                  # inits missing agents, then decays every dynamic priority by 1
    get_priority(agent) -> float
    get_base(agent) -> float        # what set_base last wrote — read before the -inf demotion
    set_base(agent, p)              # writes both _base and _dynamic immediately

def run_pibt_pass(                 # algo/coordination/pibt_core.py — Algorithm 1, extracted
    grid, goals, priorities, reservations, order, processed=None,
) -> (inheritance, inherited):
    ...                             # does NOT clear `reservations`, does NOT undo boosts —
                                     # both are the caller's job (see PIBTCoordinator.plan())

class GoalReachedPolicy(Enum):        # algo/coordination/pibt_coordinator.py
    TRANSIENT   # default — goal-reached demotion undone once the agent leaves its goal
    PERMANENT   # demotion never undone — the pre-c81534e historical behaviour

class PIBTCoordinator(Coordinator):   # algo/coordination/pibt_coordinator.py
    goals: dict[Agent, Position]     # public — rebuilt each tick from the intent; read by renderers
    _reservations: ReservationTable
    _priorities: PriorityManager
    _last_intent: dict[int, tuple]   # last (goal, priority) per agent — for the re-seed guard
    _demoted: dict[Agent, float]     # base priority overwritten by the -inf demotion, kept to undo it
                                      # under TRANSIENT (see goal_reached_policy below)

    __init__(goal_reached_policy: GoalReachedPolicy = GoalReachedPolicy.TRANSIENT)
    plan(agents, grid, intent) -> PlanResult
    _apply_intent(agents, intent)          # rebuild goals; re-seed base priority only on change
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

for _ in range(30):
    result = sim.step()      # PlanResult: positions + PIBT diagnostics
```
This snippet exists to show the coordinator/dispatcher wiring, not as a turnkey entry point —
there is currently no scripting layer above `algo`/`mrta` (see `TODO.md`). `sim_many_pibt.py`
wires a `Simulation` by hand the same way, at benchmark scale.

**Internal mechanics:**
- Goals are rebuilt each tick from `intent.goals` (an agent with no goal stays in place).
- **Re-seed guard**: the base priority is re-seeded from `intent.priorities` **only** when an agent's goal or business priority changed since last tick — otherwise the dynamic priority drift (anti-starvation) would be wiped. This is the crux of keeping the coordinator stateless about allocation while stateful about navigation.
- Dynamic priorities decay by 1 every step -> prevents starvation.
- An agent at its goal gets base priority `-inf` (processed last, prefers to stay). Whether that
  demotion is later undone is `goal_reached_policy`, chosen by the caller at construction —
  **not** something the coordinator decides, because only the caller (the dispatcher / the
  scenario's goal regime) knows whether goals ever move again:
  - **`TRANSIENT`** (default): "at its goal" is a *state*, so the overwritten base is saved in
    `_demoted` and restored the moment the state stops holding — the goal moved, or inheritance
    pushed the agent off it. Mandatory under a rotating-goal regime (MRTA/lifelong): an agent
    that just finished a task must be able to contest a cell again to start the next one.
  - **`PERMANENT`**: the demotion is a one-way write, `_demoted` is never popped by this loop.
    Measurably the better heuristic under a *static* goal regime (5x5 grid, 30 seeds: matches
    TRANSIENT up to 0.20 occupancy, up to +0.17 success rate at maximum occupancy) — an agent
    that will never be asked to move again is a better fit as a soft, non-contesting obstacle.
  Either way, an explicit re-seed from a fresh `intent` (goal or priority actually changed) still
  pops `_demoted` and overrides the demotion in `_apply_intent` — that guard is independent of
  the policy. The inheritance-boost undo at the end of `plan()` (the `inherited` bases returned
  by `run_pibt_pass`, restored unconditionally every tick) is a separate mechanism, fixed in
  `fb3303c`, and applies under both policies unconditionally.
- Priority Inheritance: if agent i wants k's cell, `set_base(k, get_priority(i) + EPSILON)` then `pibt_core._pibt(k, i, ...)` recurses.
- Backtracking: if k cannot move, i tries another candidate cell (`ReservationTable.release`).
- Obstacles are detected via `entity.blocks_movement and entity.active` on the grid's static entities.

---

### Static-mode-only limitation — `PIBTPlusCoordinator` and `LaCAMCoordinator`

Both are **batch** algorithms: they solve one fixed start→goal joint configuration by
searching ahead over several ticks before committing to a single move — incompatible with
this project's MRTA mode, which reassigns agent goals continuously (these are *joint*
algorithms, so one agent's goal changing invalidates the whole solved path for every
agent). They only support `--mode static` (goals fixed for the run's lifetime), enforced
twice: `ScenarioConfig.__post_init__` rejects `algo in ("pibt+", "lacam")` with
`mode != "static"`, and each coordinator's `plan()` independently raises `RuntimeError` if
it ever sees `intent.goals` change relative to what its cached path was built for — the
second guard catches any hand-rolled `Simulation` that bypasses the factory (the way
`sim_many_pibt.py` already does). MRTA/dynamic-goal support (recomputing the joint path on
every goal change) is an explicit, undone follow-up, not silently unsupported.

Both work the same way: on the first `plan()` call, solve the whole joint path once
against a **scratch** grid/agents clone (`algo/coordination/_scratch.py`'s
`build_scratch_grid`, never the live grid), cache it as `list[dict[int, Position]]`, then
every later call just pops the next cached configuration and returns it as a `PlanResult`.

```python
class PIBTPlusCoordinator(Coordinator):       # algo/coordination/pibt_plus_coordinator.py
    __init__(stall_patience: int | None = None, hard_cap: int | None = None)
    plan(agents, grid, intent) -> PlanResult    # cache-replay
    _solve(agents, grid, intent) -> list[Config]
    _run_pibt_phase(scratch_sim, goals) -> (joint_path, remaining_agent_ids)
```

Phase 1 runs a plain `PIBTCoordinator` inside a throwaway `Simulation`, ticking until every
agent is at goal or a stall/cap heuristic gives up — there is no closed-form T_min bound in
this codebase (no graph-diameter utility), so `stall_patience` (ticks with no per-agent
Manhattan improvement) and `hard_cap` stand in for it; this is a documented deviation from
the paper's bound, not an oversight. Phase 2 hands whichever agents remain to
`PushAndSwapCoordinator` (`algo/coordination/push_and_swap.py`, internal — not
re-exported), swapped onto the *same* scratch `Simulation` instance (`coordinator` is a
plain mutable attribute) so it continues from exactly where phase 1 stopped.
`PushAndSwapCoordinator` itself simplifies the textbook algorithm two ways, documented in
its module docstring: no tree-structured swap gadget (a boxed-in blocker falls back to a
multi-tick relocation to the nearest free cell instead) and no vertex-swap (kept consistent
with `PIBTCoordinator`, which never produces one either). One consequence, verified directly
rather than left abstract: the mover being solved always advances *this* tick — only the
blocker is ever relocated, the mover never waits or retreats — so a blocker cornered in a
dead end whose one neighbor is exactly the mover's own cell has nowhere to go regardless of
free space elsewhere, and raises. A plain dead-end corridor with two agents swapping ends
can land in exactly that configuration; `LaCAMCoordinator` resolves the same scenario (its
DFS finds one agent retreating fully to its own start before the other advances — it is not
committed to one fixed solving order). Prefer LaCAM over PIBT+ for corridor-heavy layouts.
Well-formedness is otherwise not validated anywhere in this codebase; an unsolvable instance
raises rather than looping forever.

```python
class LaCAMCoordinator(Coordinator):          # algo/coordination/lacam_coordinator.py
    __init__(node_cap: int = 20000)
    plan(agents, grid, intent) -> PlanResult    # cache-replay, identical shape to PIBT+
    _solve(agents, grid, intent) -> list[Config]     # DFS over HighLevelNode
    _generate_successor(config, grid, goals, fixed) -> Config | None
```

`HighLevelNode`/`is_goal_config`/`config_key` live in `algo/coordination/lacam_config.py`.
The low level (`_generate_successor`) is where the shared extraction pays for itself: it
builds a fresh `ReservationTable`/`PriorityManager` per call (no state leaking between DFS
branches), pre-seeds one agent's forced next cell via `reservations.reserve(...)`, marks
that agent `processed` so `pibt_core.run_pibt_pass` never gives it a fresh attempt, and
reads back everyone's reservation afterwards. One edge case worth knowing: an agent
displaced from the fixed cell that ends up fully boxed in falls back to "stay in place" —
which is exactly the fixed cell — and `ReservationTable.reserve()` would silently overwrite
the pre-seeded entry, since that displaced agent was never part of the recursion that would
normally notice and retry a clobbered reservation. `_generate_successor` checks for this
explicitly after the pass and treats it as an infeasible constraint (returns `None`,
prompting the DFS to try a different one) rather than let it corrupt the search silently.

**Adding a new Coordinator:**
```python
# in algo/coordination/my_algo.py
from core import Coordinator, PlanResult

class MyAlgo(Coordinator):
    def plan(self, agents, grid, intent) -> PlanResult:
        positions = {a.agent_id: intent.goals.get(a.agent_id, a.position) for a in agents}
        return PlanResult(positions=positions, moves={...})
```
Plug it in with a dispatcher that supplies the goals, e.g. `Simulation(grid, coordinator=MyAlgo(), dispatcher=StaticDispatcher(goals={...}))`. If the new algorithm needs a constrained PIBT pass (a fixed next cell for one agent, the rest resolved around it), reuse `algo/coordination/pibt_core.run_pibt_pass` — see `LaCAMCoordinator._generate_successor` for the shape — rather than re-deriving Algorithm 1 again.

---

### `algo/allocation/`
```python
class EasiestAllocator(Allocator):         # THE DEFAULT — nearest free robot wins
class RandomAllocator(Allocator):          # baseline — RandomAllocator(seed=None)
class KDTreeGreedyAllocator(Allocator):    # design stub — raises NotImplementedError
```

**`EasiestAllocator`** serves tasks **highest priority first**, each taking the closest robot
still free. Three decisions worth keeping:

- **Greedy, not optimal.** An early task can strand a later one with a distant robot; a
  Hungarian assignment would avoid that at O(n³) and far more machinery. Allocation runs every
  tick and `FleetManager`'s watchdog already recovers from a bad pairing, so the trade is
  deliberate — it is the sensible default, not the last word.
- **Manhattan, not path length.** Exact on a 4-connected grid without obstacles, a lower bound
  otherwise. Consulting the planner for a true distance would make allocation depend on
  navigation — precisely the coupling `DispatchIntent` exists to prevent — and would give the
  allocator its own notion of *reachable*, rival to the planner's. The task lifecycle refuses
  that on purpose: it observes absence of progress instead of proving reachability up front.
- **Deterministic ties** (`(distance, agent_id)`, task order made total by `task_id`). It draws
  no random numbers at all, so allocation stays *inside* the seed and two runs of the same
  scenario are comparable.

**`RandomAllocator`** is the distance-blind baseline, kept to compare against. Its RNG is
**owned** (`random.Random(seed)`), not the module-level global: drawing from the global one
made two runs of the same `--seed` disagree — the scenario was reproducible, the allocation was
not. `seed=None` restores the unseeded behaviour explicitly, for whoever actually wants it.

`KDTreeGreedyAllocator` is intentionally unimplemented: the indexing strategy (rebuild cost per
dispatch cycle, tie-breaking, distance metric on a discrete grid) needs discussion first. It is
the same *idea* as `EasiestAllocator` — nearest free robot — with a spatial index instead of a
linear scan, i.e. an optimisation of a class that now exists and costs O(tasks × agents) per
tick. Implement it when that scan is measured to matter, not before.

Neither allocator filters eligibility — `FleetManager` has already done that before calling
them; see [`../mrta/AGENT.md`](../mrta/AGENT.md).

`python sim_many_mrta.py` sweeps grid × agents × allocator × seeds and is the way to compare
them.
