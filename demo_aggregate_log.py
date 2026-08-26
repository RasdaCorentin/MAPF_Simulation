#!/usr/bin/env python3
"""
demo_aggregate_log.py — runs the same 3x3 PIBT scenario several times,
feeding each run's trace and summary through one CompositeExporter.

Each run writes its own timestamped trace under log/trace/, and
appends one row to the shared log/aggregate.csv — run this a few
times and watch aggregate.csv grow instead of being overwritten.

Run with:
    python3 demo_aggregate_log.py
"""

from datetime import datetime
from pathlib import Path

from core import Agent, Coordinates2D, Grid2D, WorldEngine
from export import AggregateCsvExporter, CompositeExporter, TraceCsvExporter
from pibt import GoalReachedPolicy, OneShotGoalDispatcher, PIBTPlanner

GRID_SIZE = 3
START = Coordinates2D(0, 0)
GOAL = Coordinates2D(2, 2)
MAX_STEPS = 20
N_RUNS = 3

LOG_DIR = Path(__file__).parent / "log"
AGGREGATE_PATH = LOG_DIR / "aggregate.csv"


def run_once(run_id: int) -> None:
    trace_path = LOG_DIR / "trace" / f"{datetime.now():%Y-%m-%d_%H%M%S}_{run_id}.csv"

    grid = Grid2D(GRID_SIZE, GRID_SIZE)
    agent = Agent(0, START)
    dispatcher = OneShotGoalDispatcher({0: GOAL})
    planner = PIBTPlanner(goal_reached_policy=GoalReachedPolicy.PERMANENT, orientation=True)
    trace = TraceCsvExporter(str(trace_path))
    aggregate = AggregateCsvExporter(str(AGGREGATE_PATH), trace)
    exporter = CompositeExporter([trace, aggregate])
    engine = WorldEngine(grid, planner, dispatcher, exporter=exporter)
    engine.register_agent(agent)

    for step in range(1, MAX_STEPS + 1):
        engine.advance_time_step()
        if agent.position == GOAL:
            break

    engine.close()
    print(f"run {run_id}: reached {agent.position} -> {trace_path.name}")


def main() -> None:
    for run_id in range(1, N_RUNS + 1):
        run_once(run_id)
    print(f"\nAppended {N_RUNS} rows to {AGGREGATE_PATH}")


if __name__ == "__main__":
    main()
