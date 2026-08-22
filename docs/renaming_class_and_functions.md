# Renaming proposal — classes & functions

Proposal only, nothing applied to code. Casing: `snake_case` functions/methods, `PascalCase`
classes. `name | new_name` = proposed rename; bare `name` = kept as-is.

### core/entities/position.py
```
Position | Coordinates2D
	__add__
	__repr__
```

### core/entities/entity.py
```
WorldEntity | SpatialEntity
	__init__
	cells
	active | is_active
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
Zone | NamedRegion
	__init__
	cells
	contains
	__repr__
```

### core/environment/grid.py
```
Grid | SpatialIndex
	__init__
	is_valid | is_within_bounds
	is_blocked
	place
	remove | unindex
	get_agent_at | agent_at
	get_entities_at | entities_at
	get_all | all_of_kind
	__repr__
```

### core/engine/coordinator.py
```
Coordinator | PathPlanner
	plan
```

### core/engine/dispatcher.py
```
Dispatcher | MissionOrchestrator
	dispatch | assign_missions
```

### core/engine/dispatch_intent.py
```
DispatchIntent | AssignmentManifest
```

### core/engine/plan_result.py
```
PlanResult | StepOutcome
```

### core/engine/simulation.py
```
Simulation | WorldEngine
	__init__
	add_agent | register_agent
	add_object | spawn_static_obstacle
	_validate | _validate_plan
	step | advance_time_step
	__repr__
```

### core/engine/static_dispatcher.py
```
StaticDispatcher | FixedGoalDispatcher
	__init__
	dispatch | assign_missions
```

### mrta/task.py
```
TaskState | MissionState
Task | Mission
	__eq__
	__hash__
```

### mrta/task_source.py
```
TaskSource | MissionSource
	poll
```

### mrta/queue_task_source.py
```
QueueTaskSource | QueueMissionSource
	__init__
	push
	push_many
	poll
```

### mrta/random_task_source.py
```
RandomTaskSource | RandomMissionSource
	__init__
	poll
```

### mrta/scripted_task_source.py
```
ScriptedTaskSource | ScriptedMissionSource
	__init__
	poll
```

### mrta/composite_task_source.py
```
CompositeTaskSource | CompositeMissionSource
	__init__
	poll
```

### mrta/allocator.py
```
Allocator | AssignmentStrategy
	allocate | match_missions_to_units
```

### mrta/fleet_manager.py
```
FleetManager | TaskDrivenOrchestrator
	__init__
	dispatch | assign_missions
	set_priority | set_mission_priority
	_complete | _finalize_arrived_missions
	_watchdog | _release_stalled_assignees
	_prune | _archive_terminal_missions
	_intake | _intake_new_missions
	_allocate | _run_allocation_pass
	_build_intent | _compile_assignment_manifest
	_by_eligibility | _filter_eligible_units
	_is_obstructed | _target_is_unreachable
	_manhattan | ✕ merge into manhattan_distance() (core/entities/position.py)
```

### algo/allocation/easiest_allocator.py
```
EasiestAllocator | NearestUnitAssignment
	allocate | match_missions_to_units
	_manhattan | ✕ merge into manhattan_distance()
```

### algo/allocation/kdtree_greedy_allocator.py
```
KDTreeGreedyAllocator | KDTreeNearestAssignment
	__init__
	allocate | match_missions_to_units
	_nearest_free | _nearest_free_unit
```

### algo/allocation/random_allocator.py
```
RandomAllocator | RandomAssignment
	__init__
	allocate | match_missions_to_units
```

### algo/coordination/lacam_config.py
```
HighLevelNode | LaCAMSearchNode
	__init__
(module-level)
	is_goal_config
	config_key
```

### algo/coordination/lacam_coordinator.py
```
(module-level)
	_manhattan | ✕ merge into manhattan_distance()
LaCAMCoordinator | LaCAMPlanner
	__init__
	_goal_key | _current_goal_key
	_next_constraint | _pick_next_constraint
	_backtrack | _backtrack_search
	_solve | _run_lacam_search
	_generate_successor | _expand_successor_config
	plan
```

### algo/coordination/pibt_coordinator.py
```
GoalReachedPolicy | GoalHoldPolicy
PIBTCoordinator | PIBTPlanner
	__init__
	_apply_intent | _seed_goals_and_priorities
	plan
```

### algo/coordination/pibt_core.py
```
(module-level)
	_h | _heuristic_distance
	_pibt | _pibt_step
	run_pibt_pass
```

### algo/coordination/pibt_plus_coordinator.py
```
(module-level)
	_manhattan | ✕ merge into manhattan_distance()
	_build_scratch
PIBTPlusCoordinator | PIBTPlusPlanner
	__init__
	_goal_key | _current_goal_key
	_run_pibt_phase
	_solve | _run_push_and_swap_phase
	plan
```

### algo/coordination/priority_manager.py
```
PriorityManager | PriorityTracker
	__init__
	update | decay_priorities
	get_priority | priority_of
	get_base | base_of
	set_base
```

### algo/coordination/push_and_swap.py
```
(module-level)
	_manhattan | ✕ merge into manhattan_distance()
	_passable | _is_passable
PushAndSwapCoordinator | PushAndSwapPlanner
	__init__
	_bfs | _bfs_shortest_path
	_try_push | _try_push_chain
	plan
	_advance_relocation
	_result | _build_result
```

### algo/coordination/random_walk.py
```
RandomWalkCoordinator | RandomWalkPlanner
	plan
```

### algo/coordination/reservation_table.py
```
ReservationTable | CellReservationLedger
	__init__
	reserve | reserve_cell
	release | release_cell
	get_reserving_agent | agent_holding
	get_reservation | reservation_for
	clear
```

### algo/coordination/_scratch.py
```
(module-level)
	build_scratch_grid
```

---

Needs sign-off before this goes further: keep `Agent` as-is? keep `PIBT`/`LaCAM`/push-and-swap
identity in planner names? confirm `snake_case`?
