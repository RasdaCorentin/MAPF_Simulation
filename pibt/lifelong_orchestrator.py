from typing import Optional, TYPE_CHECKING

from core import AssignmentManifest, Coordinates2D, MissionOrchestrator, Objective

if TYPE_CHECKING:
    from core import Agent, Grid2D


class LifelongGoalOrchestrator(MissionOrchestrator):
    """MissionOrchestrator for the lifelong MAPF regime: targets arrive from
    outside, one per agent, at any time.

    Where OneShotGoalDispatcher hands out one goal per agent for the whole
    run, this one holds one *mutable* target slot per agent, set through
    set_target() by whichever caller owns the goal source — an operator
    click translated by sim_dotbot_mrta.py's ManualClickTranslator, the use
    case this class actually serves. assign_missions() only reflects the
    current slot state into an AssignmentManifest each tick; it never
    decides what an agent's next target should be, so there is no shared
    pool and nothing to arbitrate between agents.

    Deliberately minimal: no eligibility classes, no pluggable allocation
    strategy, no stall watchdog, no collision check across targets — see
    diagrammes/Class_Diagram/Pibt/class_diag_commented.puml for the design
    note this implements and the full trade-off. Two consequences to know
    before use:
    - nothing prevents two agents from being set to the same target
      position — rejecting that is an operator-input concern
      (ManualClickTranslator/MRTASession), not this class's job;
    - an agent whose target turns out unreachable is parked on it forever
      — there is no progress check behind assign_missions().
    See mrta/TaskDrivenOrchestrator (removed, see TODO.md) for what closing
    either gap actually needs.

    Requires PIBTPlanner's GoalReachedPolicy.TRANSIENT (its default): an
    agent demoted to -inf priority on arrival must be undemoted the
    instant it is re-targeted, or it can never contest a cell again.
    """

    def __init__(self, priorities: Optional[dict[int, float]] = None) -> None:
        """Input: optional fixed priorities (agent_id -> float).
        Output: None. Every agent starts with no target (parked) until
        set_target() is called for it.
        """
        self._target: dict[int, Optional[Coordinates2D]] = {}
        self._priorities = dict(priorities) if priorities is not None else {}

    def set_target(self, agent_id: int, position: Coordinates2D) -> None:
        """Input: the agent to (re-)task and its new target position.
        Output: None. Overwrites any target already set for that agent —
        a re-click on a bot already mid-route simply lands here.
        """
        self._target[agent_id] = position

    def assign_missions(
        self, agents: "list[Agent]", grid: "Grid2D", step: int
    ) -> AssignmentManifest:
        """Input: agents, grid, step (grid and step ignored).
        Output: an AssignmentManifest with one Objective per agent that
        currently has a target, each already attach_to()'d to that agent.
        An agent found standing on its target has its slot cleared to
        None and is omitted from goals this tick — it stays parked until
        set_target() is called again.
        """
        objectives = []
        for agent in agents:
            target = self._target.get(agent.agent_id)
            if target is None:
                continue
            if agent.position == target:
                self._target[agent.agent_id] = None
                continue
            objective = Objective(entity_id=agent.agent_id, position=target)
            objective.attach_to(agent)
            objectives.append(objective)
        return AssignmentManifest(goals=objectives, priorities=dict(self._priorities))
