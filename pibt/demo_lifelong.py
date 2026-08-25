"""First end-to-end run of LifelongGoalOrchestrator: a rotating goal pool.

"Lifelong" means an agent is re-tasked the instant it reaches its current
goal, drawing the next one from a shared pool — no fixed end state, unlike
``demo_one_shot.py``. Requires PIBTPlanner's default
``GoalReachedPolicy.TRANSIENT``: an agent parked -inf on arrival must be
undemoted the instant it is re-tasked, or it could never move again.

Three agents share a four-position goal pool on a small grid, so the pool
outlives any single agent's path and reassignments keep happening for the
whole run.

Run with:
    python -m pibt.demo_lifelong
"""

from __future__ import annotations

from core import Agent, Coordinates2D, Grid2D, WorldEngine

from .lifelong_orchestrator import LifelongGoalOrchestrator
from .pibt_planner import PIBTPlanner

GRID_SIZE = 5
STEPS = 60

GOAL_POOL = [
    Coordinates2D(4, 4),
    Coordinates2D(0, 4),
    Coordinates2D(4, 0),
    Coordinates2D(0, 0),
]

START_POSITIONS: dict[int, Coordinates2D] = {
    0: Coordinates2D(0, 0),
    1: Coordinates2D(4, 0),
    2: Coordinates2D(2, 4),
}


def build_engine() -> WorldEngine:
    grid = Grid2D(GRID_SIZE, GRID_SIZE)
    orchestrator = LifelongGoalOrchestrator(list(GOAL_POOL))
    planner = PIBTPlanner()  # GoalReachedPolicy.TRANSIENT (default) — required here
    engine = WorldEngine(grid, planner, orchestrator)

    for agent_id, start in START_POSITIONS.items():
        engine.register_agent(Agent(agent_id, start))

    return engine


def run_demo() -> int:
    """Output: number of goal reassignments (= goals reached, excluding
    each agent's first assignment) observed across STEPS."""
    engine = build_engine()
    previous_goal: dict[int, Coordinates2D] = {}
    reassignments = 0

    print(f"Grid {GRID_SIZE}x{GRID_SIZE}, goal_pool={GOAL_POOL}")

    for step in range(1, STEPS + 1):
        outcome = engine.advance_time_step()

        current_goal = {
            objective.assignee.agent_id: objective.position
            for objective in engine.last_intent.goals
            if objective.assignee is not None
        }
        for agent_id, goal in current_goal.items():
            if agent_id in previous_goal and previous_goal[agent_id] != goal:
                reassignments += 1
        previous_goal = current_goal

        positions = {a.agent_id: a.position for a in engine.agents}
        print(f"step {step:2d}  positions={positions}  goals={current_goal}  order={outcome.order}")

    print(f"{reassignments} goal reassignments across {STEPS} steps.")
    return reassignments


if __name__ == "__main__":
    run_demo()
