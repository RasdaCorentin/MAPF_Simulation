"""
CompositeExporter — fans record()/flush() out to several Exporters.
WorldEngine.exporter still holds exactly one object; this is that one
object, not a change to the seam itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core import Exporter

if TYPE_CHECKING:
    from core import Agent, AssignmentManifest, Grid2D, StepOutcome


class CompositeExporter(Exporter):
    """Forwards every record()/flush() call to each wrapped Exporter,
    in the order given."""

    def __init__(self, exporters: list[Exporter]) -> None:
        """Input: the exporters to fan out to — at least one.
        Output: None.
        """
        self._exporters = exporters

    def record(
        self,
        step: int,
        agents: list["Agent"],
        grid: "Grid2D",
        outcome: "StepOutcome",
        intent: "AssignmentManifest",
    ) -> None:
        """Input: see Exporter.record().
        Output: None. Calls record() on every wrapped exporter."""
        for exporter in self._exporters:
            exporter.record(step, agents, grid, outcome, intent)

    def flush(self) -> None:
        """Input: none.
        Output: None. Calls flush() on every wrapped exporter, in
        order — a later exporter reading an earlier one's accumulated
        state (e.g. AggregateCsvExporter reading a TraceCsvExporter)
        only needs that state complete by its own flush(), not by the
        earlier exporter's flush() specifically."""
        for exporter in self._exporters:
            exporter.flush()
