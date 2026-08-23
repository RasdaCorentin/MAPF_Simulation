from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .dispatch_intent import AssignmentManifest

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..environment.grid import Grid2D


class MissionOrchestrator(ABC):
    """Pre-planning hook run by ``WorldEngine.advance_time_step()`` before the planner plans.

    A mission orchestrator reads the world state at the current step and
    returns an ``AssignmentManifest`` — the absolute goals/priorities wanted
    this tick. It never touches the planner: the manifest is data, handed by
    WorldEngine to ``PathPlanner.plan()``. Keeping this abstraction in
    ``core`` lets ``WorldEngine`` own the tick order (assign_missions -> plan)
    without importing whatever implements this seam — the same
    dependency-inversion pattern as ``PathPlanner``.
    There is no concrete implementation in the repository right now.
    """

    @abstractmethod
    def assign_missions(
        self, agents: list["Agent"], grid: "Grid2D", step: int
    ) -> AssignmentManifest:
        """Input: all simulated agents, the grid, and the current step.
        Output: an AssignmentManifest with the complete goals/priorities for
        this tick (no side effect on the planner).
        """
        ...
