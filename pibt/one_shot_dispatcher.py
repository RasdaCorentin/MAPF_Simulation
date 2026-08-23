from typing import Optional, TYPE_CHECKING

from core import AssignmentManifest, Coordinates2D, MissionOrchestrator, Objective

if TYPE_CHECKING:
    from core import Agent, Grid2D


class OneShotGoalDispatcher(MissionOrchestrator):
    """Minimal MissionOrchestrator for a fixed one-shot goal map.

    Scaffolding local to pibt/'s demo — not a general-purpose replacement
    for core's own FixedGoalDispatcher, which was dropped rather than
    adapted (see core/AGENT.md and 4e0c51f): building AssignmentManifest's
    Objectives at construction time, before any Agent exists to
    attach_to(), does not fit goals: list[Objective]. Building them lazily
    inside assign_missions() sidesteps that, since agents are available by
    then — just enough to drive PIBTPlanner's one-shot demo.
    """

    def __init__(
        self,
        goals: dict[int, Coordinates2D],
        priorities: Optional[dict[int, float]] = None,
    ) -> None:
        """Input: fixed goal positions (agent_id -> Coordinates2D) and
        optional fixed priorities (agent_id -> float).
        Output: None.
        """
        self._goal_positions = dict(goals)
        self._priorities = dict(priorities) if priorities is not None else {}

    def assign_missions(
        self, agents: "list[Agent]", grid: "Grid2D", step: int
    ) -> AssignmentManifest:
        """Input: agents, grid, step (grid and step ignored).
        Output: an AssignmentManifest with one Objective per agent that
        has a configured goal, each already attach_to()'d to that agent.
        """
        objectives = []
        for agent in agents:
            position = self._goal_positions.get(agent.agent_id)
            if position is None:
                continue
            objective = Objective(entity_id=agent.agent_id, position=position)
            objective.attach_to(agent)
            objectives.append(objective)
        return AssignmentManifest(goals=objectives, priorities=dict(self._priorities))
