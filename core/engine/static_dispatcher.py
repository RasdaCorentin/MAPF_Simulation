from typing import Optional, TYPE_CHECKING

from ..entities.position import Coordinates2D
from .dispatch_intent import AssignmentManifest
from .dispatcher import MissionOrchestrator

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..environment.grid import Grid2D


class FixedGoalDispatcher(MissionOrchestrator):
    """Trivial mission orchestrator: always returns the same fixed manifest.

    Fallback for scenarios that do not need task allocation (MRTA): fixed
    goals and optional priorities are configured once at construction, and
    the same immutable ``AssignmentManifest`` is returned on every tick.
    """

    def __init__(
        self,
        goals: dict[int, Coordinates2D],
        priorities: Optional[dict[int, float]] = None,
    ) -> None:
        """Input: fixed goals (agent_id -> Coordinates2D) and optional
        fixed priorities (agent_id -> float).
        Output: None.
        """
        self._intent = AssignmentManifest(
            goals=dict(goals),
            priorities=dict(priorities) if priorities is not None else {},
        )

    def assign_missions(
        self, agents: "list[Agent]", grid: "Grid2D", step: int
    ) -> AssignmentManifest:
        """Input: agents, grid, step (all ignored).
        Output: the same fixed AssignmentManifest, every tick.
        """
        return self._intent
