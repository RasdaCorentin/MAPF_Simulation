# mrta/ — Multi-Robot Task Allocation

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`mrta/` decides *who does what*. It sits on `core` alone: allocation and navigation meet
only through `AssignmentManifest`, which is what lets any allocation strategy run under any planner.

```python
class MissionState(Enum):          # mrta/task.py
    PENDING, ASSIGNED, DONE, FAILED

class Mission:                     # mrta/task.py — hashable via task_id
    task_id: int                   # stamped by TaskDrivenOrchestrator at intake, not by the source
    target: Coordinates2D
    priority: float
    state: MissionState
    assignee: Agent | None
    created_step: int
    eligible: frozenset[int] | None    # agent_ids allowed to take it (None = anyone)
    attempts: int                      # assignees burned through so far
    best_distance: int | None          # best Manhattan distance ever reached
    last_improvement_step: int         # step at which best_distance last improved

class MissionSource(ABC):          # mrta/task_source.py
    fetch_new_missions(current_step) -> list[Mission]

class QueueMissionSource(MissionSource):     # push / push_many, fetch_new_missions() drains and empties
class RandomMissionSource(MissionSource):    # (grid, every, count, seed)
class ScriptedMissionSource(MissionSource):  # ({step: [Mission]})
class CompositeMissionSource(MissionSource): # (*sources) — polled in order, concatenated

class AssignmentStrategy(ABC):     # mrta/allocator.py
    match_missions_to_units(pending, free, grid) -> dict[Mission, Agent]

class TaskDrivenOrchestrator(MissionOrchestrator):    # mrta/fleet_manager.py — concrete MissionOrchestrator
    source: MissionSource
    allocator: AssignmentStrategy
    patience: int                  # steps without progress before releasing an assignee
    max_attempts: int              # assignees a mission may burn before it is FAILED
    tasks: list[Mission]
    completed_count: int
    failed_count: int

    assign_missions(agents, grid, step) -> AssignmentManifest
    #   _finalize_arrived_missions -> _release_stalled_assignees -> _archive_terminal_missions
    #   -> _intake_new_missions -> _run_allocation_pass -> _compile_assignment_manifest
    set_mission_priority(task_id, priority)
    _finalize_arrived_missions(agents)   # ASSIGNED -> DONE once the assignee stands on the target
    _release_stalled_assignees(step)     # releases stalled assignees; FAILED past max_attempts
    _archive_terminal_missions()         # drops terminal missions, counting them on the way out
    _intake_new_missions(step, grid)     # stamps ids; FAILED at once if the target is unreachable
    _run_allocation_pass(agents, grid)   # one allocator call per eligibility class, restricted first
    _compile_assignment_manifest() -> AssignmentManifest   # goals/priorities of the ASSIGNED missions
    _filter_eligible_units(pending)      # static — groups pending missions, restricted classes FIRST
    _target_is_unreachable(pos, grid)    # static helper — manhattan_distance() lives in core now
```

**Mission lifecycle** — `PENDING -> ASSIGNED -> DONE` is nominal; `FAILED` is terminal for
abandoned work. Two guards close the allocation deadlock a plain three-state lifecycle left open
(an unreachable target consumed its assignee *forever*, since `_run_allocation_pass` excludes ASSIGNED
agents from the free pool — a fleet silently losing robots while looking healthy):

- **static, at intake** — a target off the grid or under a blocking entity is rejected outright;
- **dynamic, the watchdog** — an assignee that has not improved its Manhattan distance to the
  target for `patience` steps is released and the mission retried; past `max_attempts` distinct
  assignees, the *target* is blamed and the mission FAILED.

We deliberately do **not** try to *prove* a target reachable: reachability is not static in a
world with `appear_at`, and proving it would duplicate the planner with a rival notion of
"reachable". We observe the absence of progress instead. Terminal missions are pruned but
**counted** — dropping work silently would hide the very deadlock this closes.

The watchdog belongs to `TaskDrivenOrchestrator` because it is the only component seeing a mission *across*
ticks; in the planner it would re-couple navigation with allocation semantics, exactly what
`AssignmentManifest` separated.

**Eligibility** — `Mission.eligible` restricts who may take a mission, so a caller can send a
*specific* batch somewhere. `_run_allocation_pass()` groups pending missions by eligibility class and calls
the allocation strategy once per class, **restricted classes first** (otherwise an unrestricted mission could
steal a reserved agent), removing matched agents from the pool between calls. The constraint
lives on the *request*, not on the matching *strategy*, so the `AssignmentStrategy` interface is
untouched and new strategies need no adaptation.

`TaskDrivenOrchestrator` holds **no planner reference**: it is pure w.r.t. the engine. It returns an `AssignmentManifest`, and `WorldEngine.advance_time_step()` passes it to `plan()`. `WorldEngine` owns the ordering: `WorldEngine(grid, coordinator, dispatcher=orchestrator)` and `advance_time_step()` runs `assign_missions()` before `plan()` every tick — the caller no longer sequences them by hand.

---

---

## Eligibility and the allocator contract

No `AssignmentStrategy` implementation filters eligibility — that guarantee holds regardless of which
one is plugged in. `TaskDrivenOrchestrator._filter_eligible_units()` groups pending missions by eligibility class
and calls the strategy once per class, **restricted classes first**, so an unrestricted mission
cannot steal a reserved agent. The constraint lives on the *request*, not on the matching
*strategy* — which is why the `AssignmentStrategy` interface never had to grow for it, and why a new
strategy needs no adaptation. There is currently no concrete `AssignmentStrategy` at all — see
`TODO.md`.

---

## Domain vocabulary — settles a naming mistake

A **rack** is the **crate a robot loads or does not load onto itself** — a payload, *not* a
region of the map. The three operational regions are therefore the *loading station*, the
*working space*, and the *empty-rack area* (where empty crates are parked): the last is named
after what sits in it, not after a kind of region. **Nothing in `core` models these regions any
more** — the multi-cell `Zone` entity that used to (`core.Zone`) was removed once nothing
depended on it; see [`core/AGENT.md`](../core/AGENT.md). Reintroducing that vocabulary means
reintroducing a multi-cell `WorldEntity` first.

Nothing in the code models a rack yet. A `Rack` entity carried by an `Agent` (load / unload,
`Agent.carrying: Rack | None`) is the obvious next step and would change the mission lifecycle —
a job becomes "fetch a rack here, drop it there" rather than "stand on this cell". **Not in
scope now**; recorded so the vocabulary does not have to be un-learned later.
