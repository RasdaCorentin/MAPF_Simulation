"""First end-to-end run of PIBTPlanner: a one-shot goal map.

"One-shot" means every agent gets a single fixed goal for the whole run —
no rotating tasks, no mrta — so the mission side is the trivial
``OneShotGoalDispatcher`` (local to this package — core's own
``FixedGoalDispatcher`` was dropped in 4e0c51f, see
``one_shot_dispatcher.py``) rather than a ``TaskDrivenOrchestrator``.
This is the smallest scenario that exercises the full tick
(assign missions -> plan -> move) with a real PathPlanner plugged in.

Three agents cross through the center of the grid, forcing PIBT's
priority inheritance to kick in (a higher-priority agent pushes a
lower-priority one out of its way) rather than just walking three
independent straight lines.

Note: ``_h()`` in ``pibt_core.py`` is a raw Manhattan-distance heuristic,
not obstacle-aware — faithfully ported from the pre-``algo/``-removal
implementation. A single-cell obstacle sitting exactly on a corridor can
put two detour directions at equal heuristic distance, and the fixed
``DIRS`` tie-break can then oscillate an agent between two cells forever
instead of committing to one detour. This demo's scenario is deliberately
obstacle-free so it does not hit that corner case.

Run with:
    python -m pibt.demo_one_shot
"""

from __future__ import annotations

from core import Agent, Coordinates2D, Grid2D, WorldEngine

from .one_shot_dispatcher import OneShotGoalDispatcher
from .pibt_planner import GoalReachedPolicy, PIBTPlanner

GRID_SIZE = 5
MAX_STEPS = 30

# Agent id -> (start, goal). All three paths cross near the grid's center,
# so PIBT must resolve the conflict instead of each agent walking a free
# straight line.
SCENARIO: dict[int, tuple[Coordinates2D, Coordinates2D]] = {
    0: (Coordinates2D(0, 0), Coordinates2D(4, 4)),
    1: (Coordinates2D(4, 0), Coordinates2D(0, 4)),
    2: (Coordinates2D(2, 4), Coordinates2D(2, 0)),
}


def build_engine() -> WorldEngine:
    grid = Grid2D(GRID_SIZE, GRID_SIZE)
    goals = {agent_id: goal for agent_id, (_, goal) in SCENARIO.items()}
    dispatcher = OneShotGoalDispatcher(goals)
    planner = PIBTPlanner(goal_reached_policy=GoalReachedPolicy.PERMANENT)
    engine = WorldEngine(grid, planner, dispatcher)

    for agent_id, (start, _) in SCENARIO.items():
        engine.register_agent(Agent(agent_id, start))

    return engine


def run_demo() -> bool:
    """Output: True if every agent reached its goal within MAX_STEPS."""
    engine = build_engine()
    goals = {agent_id: goal for agent_id, (_, goal) in SCENARIO.items()}

    print(f"Grid {GRID_SIZE}x{GRID_SIZE}, goals={goals}")

    for step in range(1, MAX_STEPS + 1):
        outcome = engine.advance_time_step()
        positions = {a.agent_id: a.position for a in engine.agents}
        at_goal = all(positions[aid] == goal for aid, goal in goals.items())

        print(f"step {step:2d}  positions={positions}  order={outcome.order}  inheritance={outcome.inheritance}")

        if at_goal:
            print(f"All agents reached their goal at step {step}.")
            return True

    print(f"Did not converge within {MAX_STEPS} steps.")
    return False


if __name__ == "__main__":
    import sys

    sys.exit(0 if run_demo() else 1)
