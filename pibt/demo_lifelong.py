"""First end-to-end run of LifelongGoalOrchestrator: externally set targets,
simulating operator clicks.

"Lifelong" means an agent can be re-targeted at any time via set_target() —
no fixed end state, unlike demo_one_shot.py. Requires PIBTPlanner's default
GoalReachedPolicy.TRANSIENT: an agent parked -inf on arrival must be
undemoted the instant it is re-targeted, or it could never move again.

There is no real ManualClickTranslator here to drive the orchestrator, so
this demo plays that role itself: whenever an agent is found standing on
the target it was last given, the demo hands it the next position from a
small rotating pool via set_target() — exactly the decision
sim_dotbot_mrta.py leaves to the operator's next click.

Run with:
    python -m pibt.demo_lifelong
"""

from __future__ import annotations

from itertools import cycle

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


def build_engine() -> tuple[WorldEngine, LifelongGoalOrchestrator]:
    grid = Grid2D(GRID_SIZE, GRID_SIZE)
    orchestrator = LifelongGoalOrchestrator()
    planner = PIBTPlanner()  # GoalReachedPolicy.TRANSIENT (default) — required here
    engine = WorldEngine(grid, planner, orchestrator)

    for agent_id, start in START_POSITIONS.items():
        engine.register_agent(Agent(agent_id, start))

    return engine, orchestrator


def run_demo() -> int:
    """Output: number of retargetings observed across STEPS (each agent's
    initial assignment excluded)."""
    engine, orchestrator = build_engine()
    pool = cycle(GOAL_POOL)
    assigned: dict[int, Coordinates2D] = {}
    reassignments = 0

    print(f"Grid {GRID_SIZE}x{GRID_SIZE}, goal_pool={GOAL_POOL}")

    for agent in engine.agents:
        target = next(pool)
        orchestrator.set_target(agent.agent_id, target)
        assigned[agent.agent_id] = target

    for step in range(1, STEPS + 1):
        outcome = engine.advance_time_step()

        for agent in engine.agents:
            if agent.position == assigned.get(agent.agent_id):
                target = next(pool)
                orchestrator.set_target(agent.agent_id, target)
                assigned[agent.agent_id] = target
                reassignments += 1

        positions = {a.agent_id: a.position for a in engine.agents}
        print(f"step {step:2d}  positions={positions}  targets={assigned}  order={outcome.order}")

    print(f"{reassignments} retargetings across {STEPS} steps.")
    return reassignments


if __name__ == "__main__":
    run_demo()
