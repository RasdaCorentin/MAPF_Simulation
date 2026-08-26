from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..environment.grid import Grid2D
    from .dispatch_intent import AssignmentManifest
    from .plan_result import StepOutcome


class Exporter(ABC):
    """Optional, silent-by-default seam: WorldEngine works without one.

    Unlike PathPlanner (mandatory) and MissionOrchestrator (optional but
    still a planning input), an Exporter is a pure observer — it never
    influences the tick, only watches it. ``record()`` runs once per
    tick, right after the move/rotate phases; ``flush()`` runs once,
    whenever the caller decides the run is over (``WorldEngine.close()``),
    not per tick — so an exporter that needs the whole run before it can
    write anything (e.g. one that run-length-encodes per-tick deltas
    into a compressed action string) never has to write mid-run.
    """

    @abstractmethod
    def record(
        self,
        step: int,
        agents: list["Agent"],
        grid: "Grid2D",
        outcome: "StepOutcome",
        intent: "AssignmentManifest",
    ) -> None:
        """Input: the step just applied, all simulated agents (already
        moved/rotated), the grid, the StepOutcome that produced this
        state, and the AssignmentManifest planner.plan() consumed this
        tick (goals/priorities) — the same object WorldEngine.last_intent
        holds, not a copy.
        Output: None. Called once per tick by WorldEngine.advance_time_step(),
        after the move and rotate phases.
        """
        ...

    @abstractmethod
    def flush(self) -> None:
        """Input: none.
        Output: None. Called once by WorldEngine.close(), after the run
        ends — not per tick.
        """
        ...
