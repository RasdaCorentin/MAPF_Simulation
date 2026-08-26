#!/usr/bin/env python3
"""
demo_trace_log.py — runs one PIBT scenario and logs every tick to a CSV
trace file under log/trace/.

Same 3x3 scenario used to exercise the exporter seam before: a single
agent going (0,0) -> (2,2) under PIBTPlanner(orientation=True).

Run with:
    python3 demo_trace_log.py
"""

from datetime import datetime
from pathlib import Path

from core import Agent, Coordinates2D, Grid2D, WorldEngine
from export import TraceCsvExporter
from pibt import GoalReachedPolicy, OneShotGoalDispatcher, PIBTPlanner

GRID_SIZE = 3
START = Coordinates2D(0, 0)
GOAL = Coordinates2D(2, 2)
MAX_STEPS = 20

OUT_DIR = Path(__file__).parent / "log" / "trace"


def main() -> None:
    csv_path = OUT_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}.csv"

    grid = Grid2D(GRID_SIZE, GRID_SIZE)
    agent = Agent(0, START)
    dispatcher = OneShotGoalDispatcher({0: GOAL})
    planner = PIBTPlanner(goal_reached_policy=GoalReachedPolicy.PERMANENT, orientation=True)
    exporter = TraceCsvExporter(str(csv_path))
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
    print(f"\nWrote {csv_path}")


if __name__ == "__main__":
    main()
