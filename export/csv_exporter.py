"""
CsvExporter — accumulates each tick's (position, orientation) per agent
in memory; flush() writes them as a flat CSV, one row per agent per
tick.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from core import Exporter

if TYPE_CHECKING:
    from core import Agent, Grid2D, StepOutcome

_Row = tuple[int, int, int, int, str]


class CsvExporter(Exporter):
    """Writes one row per agent per tick: step, agent_id, x, y, orientation."""

    _HEADER = ("step", "agent_id", "x", "y", "orientation")

    def __init__(self, csv_path: str) -> None:
        """Input: where to write the CSV once the run ends — parent
        directories are created if missing (e.g. "log/run.csv").
        Output: None.
        """
        self._csv_path = Path(csv_path)
        self._rows: list[_Row] = []

    def record(
        self,
        step: int,
        agents: list["Agent"],
        grid: "Grid2D",
        outcome: "StepOutcome",
    ) -> None:
        """Input: see Exporter.record().
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
