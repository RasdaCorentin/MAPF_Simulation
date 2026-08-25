#!/usr/bin/env python3
"""
demo_planviz.py — exports one PIBT run in the format PlanViz reads.

Smallest scenario that exercises the same-tick rotate+move split: a
3x3 grid, a single agent going (0,0) -> (2,2) under
PIBTPlanner(orientation=True). The path crosses a corner, so
PlanVizExporter has to turn a same-tick position+orientation change
into a genuine rotate action, not just a straight run of forwards.

Run with:
    python3 demo_planviz.py

Then view it:
    cd ~/Inria/PlanViz && python3 script/run.py --map <printed .map path> --plan <printed .json path>
"""

from pathlib import Path

from core import Agent, Coordinates2D, WorldEngine, Grid2D
from pibt import PIBTPlanner, OneShotGoalDispatcher, GoalReachedPolicy
from export import PlanVizExporter

GRID_SIZE = 3
START = Coordinates2D(0, 0)
GOAL = Coordinates2D(2, 2)
MAX_STEPS = 20

OUT_DIR = Path(__file__).parent / "runs"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    map_path = OUT_DIR / "demo_3x3.map"
    plan_path = OUT_DIR / "demo_3x3.json"

    grid = Grid2D(GRID_SIZE, GRID_SIZE)
    agent = Agent(0, START)
    dispatcher = OneShotGoalDispatcher({0: GOAL})
    planner = PIBTPlanner(goal_reached_policy=GoalReachedPolicy.PERMANENT, orientation=True)
    # ticks_per_action=10 matches PlanViz's own default (agentMaxCounter,
    # ticks per Forward/Rotate action) so the animation moves a full cell
    # per action instead of a barely-visible fraction of one — see
    # PlanVizExporter's docstring / export/AGENT.md.
    exporter = PlanVizExporter(str(map_path), str(plan_path), ticks_per_action=10)
    engine = WorldEngine(grid, planner, dispatcher, exporter=exporter)
    engine.register_agent(agent)

    print(f"{GRID_SIZE}x{GRID_SIZE} grid, agent 0: {START} -> {GOAL}")
    for step in range(1, MAX_STEPS + 1):
        engine.advance_time_step()
        print(f"  tick {step}: position={agent.position} orientation={agent.orientation.name}")
        if agent.position == GOAL:
            print(f"Reached goal at tick {step}.")
            break
    else:
        print(f"Did not reach goal within {MAX_STEPS} steps.")

    engine.close()
    print(f"\nWrote {map_path} and {plan_path}")
    print(
        f"\nView it:\n  cd ~/Inria/PlanViz && python3 script/run.py "
        f"--map {map_path.resolve()} --plan {plan_path.resolve()}"
    )


if __name__ == "__main__":
    main()
