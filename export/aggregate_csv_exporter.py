"""
AggregateCsvExporter — one CSV row per run, appended to a shared file
instead of overwritten. Reads a TraceCsvExporter's already-accumulated
positions (rows()) rather than re-reading agents itself.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from core import Coordinates2D, Exporter

if TYPE_CHECKING:
    from core import Agent, AssignmentManifest, Grid2D, StepOutcome

    from .trace_csv_exporter import TraceCsvExporter

_FIELDS = ("date", "n_agents", "ticks", "success_rate", "makespan", "deadlocks")


class AggregateCsvExporter(Exporter):
    """Tracks each agent's current goal per tick from intent.goals;
    flush() pairs that with trace.rows() to append a summary row."""

    def __init__(self, csv_path: str, trace: "TraceCsvExporter") -> None:
        """Input: where to append the summary row, and the
        TraceCsvExporter this run's position data is read from.
        Output: None.
        """
        self._csv_path = Path(csv_path)
        self._trace = trace
        self._goals: dict[tuple[int, int], Coordinates2D] = {}

    def record(
        self,
        step: int,
        agents: list["Agent"],
        grid: "Grid2D",
        outcome: "StepOutcome",
        intent: "AssignmentManifest",
    ) -> None:
        """Input: see Exporter.record(). Ignores agents, grid and
        outcome — position comes from trace.rows() at flush() time.
        Output: None. Records this tick's (agent_id -> goal) from
        intent.goals, keyed by (step, agent_id).
        """
        for objective in intent.goals:
            assignee = objective.assignee
            if assignee is not None:
                self._goals[(step, assignee.agent_id)] = objective.position

    def flush(self) -> None:
        """Input: none.
        Output: None. Appends one summary row — date, n_agents, ticks,
        success_rate, makespan, deadlocks — to csv_path, writing the
        header only if the file does not already exist.
        """
        positions_by_agent: dict[int, list[tuple[int, Coordinates2D]]] = defaultdict(list)
        for step, agent_id, x, y, _orientation in self._trace.rows():
            positions_by_agent[agent_id].append((step, Coordinates2D(x, y)))

        n_agents = len(positions_by_agent)
        ticks = max(
            (step for history in positions_by_agent.values() for step, _ in history),
            default=0,
        )

        last_arrival: dict[int, int | None] = {}
        for agent_id, history in positions_by_agent.items():
            current_goal: Coordinates2D | None = None
            arrived_current = False
            arrival_tick: int | None = None
            for step, pos in history:
                goal = self._goals.get((step, agent_id))
                if goal != current_goal:
                    current_goal = goal
                    arrived_current = False
                if goal is not None and not arrived_current and pos == goal:
                    arrived_current = True
                    arrival_tick = step
            last_arrival[agent_id] = arrival_tick

        arrived = sum(1 for tick in last_arrival.values() if tick is not None)
        row = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "n_agents": n_agents,
            "ticks": ticks,
            "success_rate": round(arrived / n_agents, 4) if n_agents else 0.0,
            "makespan": max((t for t in last_arrival.values() if t is not None), default=None),
            "deadlocks": n_agents - arrived,
        }

        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self._csv_path.exists()
        with open(self._csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
