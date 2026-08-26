"""
TraceCsvExporter — accumulates each tick's (position, orientation) per
agent in memory; flush() writes them as a flat CSV, one row per agent
per tick. Also AggregateCsvExporter's data source, via rows().
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from core import Exporter

if TYPE_CHECKING:
    from core import Agent, AssignmentManifest, Grid2D, StepOutcome

_Row = tuple[int, int, int, int, str]


class TraceCsvExporter(Exporter):
    """Writes one row per agent per tick: step, agent_id, x, y, orientation."""

    _HEADER = ("step", "agent_id", "x", "y", "orientation")

    def __init__(self, csv_path: str) -> None:
        """Input: where to write the CSV once the run ends — parent
        directories are created if missing (e.g. "log/trace/run.csv").
        Output: None.
        """
        self._csv_path = Path(csv_path)
        self._rows: list[_Row] = []

    def rows(self) -> list[_Row]:
        """Input: none.
        Output: the accumulated (step, agent_id, x, y, orientation)
        rows so far — read-only, for AggregateCsvExporter to reuse
        instead of re-reading agents itself."""
        return list(self._rows)

    def record(
        self,
        step: int,
        agents: list["Agent"],
        grid: "Grid2D",
        outcome: "StepOutcome",
        intent: "AssignmentManifest",
    ) -> None:
        """Input: see Exporter.record(). Ignores grid, outcome and
        intent — a raw trace only needs agent position/orientation.
        Output: None. Appends one row per agent for this tick.
        """
        for agent in agents:
            self._rows.append(
                (step, agent.agent_id, agent.position.x, agent.position.y, agent.orientation.name)
            )

    def flush(self) -> None:
        """Input: none.
        Output: None. Writes the accumulated rows to csv_path."""
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self._HEADER)
            writer.writerows(self._rows)
