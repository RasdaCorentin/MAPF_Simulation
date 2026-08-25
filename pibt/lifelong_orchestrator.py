from typing import Optional, TYPE_CHECKING

from core import AssignmentManifest, Coordinates2D, MissionOrchestrator, Objective

if TYPE_CHECKING:
    from core import Agent, Grid2D


class LifelongGoalOrchestrator(MissionOrchestrator):
    """MissionOrchestrator for the lifelong MAPF regime: goals keep arriving.

    Where OneShotGoalDispatcher hands out one goal per agent for the whole
    run, this one draws the next entry from a shared, rotating goal pool
    the instant an agent is found standing on its current goal — see
    diagrammes/Class_Diagram/Pibt/class_diag_commented.puml for the design
    note this implements.

    Deliberately minimal: no eligibility classes, no pluggable allocation
    strategy, no stall watchdog. _next_goal() is the only matching policy
    — FCFS by arrival order, popped from the front of the pool and pushed
    back at the end, so it never runs dry. Two consequences to know before
    use:
    - nothing prevents two agents from being handed the same goal position
      (no exclusivity across the pool);
    - an agent whose current goal turns out unreachable is parked on it
      forever — there is no progress check behind assign_missions().
    Both are accepted on the assumption that goal_pool holds only
    reachable, non-colliding positions; see mrta/TaskDrivenOrchestrator
    (removed, see TODO.md) for what closing either gap actually needs.

    Requires PIBTPlanner's GoalReachedPolicy.TRANSIENT (its default): an
    agent demoted to -inf priority on arrival must be undemoted the
    instant it is re-tasked, or it can never contest a cell again.
    """

    def __init__(
        self,
        goal_pool: "list[Coordinates2D]",
        priorities: Optional[dict[int, float]] = None,
    ) -> None:
        """Input: the rotating pool of candidate goal positions (must be
        non-empty) and optional fixed priorities (agent_id -> float).
        Output: None.
        """
        if not goal_pool:
            raise ValueError("goal_pool must not be empty")
        self._goal_pool = list(goal_pool)
        self._current_goal: dict[int, Coordinates2D] = {}
        self._priorities = dict(priorities) if priorities is not None else {}

    def assign_missions(
        self, agents: "list[Agent]", grid: "Grid2D", step: int
    ) -> AssignmentManifest:
        """Input: agents, grid, step (grid and step ignored).
        Output: an AssignmentManifest with one Objective per agent, each
        already attach_to()'d to that agent — the agent's current goal,
        re-drawn from the pool the instant it is reached.
        """
        objectives = []
        for agent in agents:
            goal = self._current_goal.get(agent.agent_id)
            if goal is None or agent.position == goal:
                goal = self._next_goal(agent)
                self._current_goal[agent.agent_id] = goal
            objective = Objective(entity_id=agent.agent_id, position=goal)
            objective.attach_to(agent)
            objectives.append(objective)
        return AssignmentManifest(goals=objectives, priorities=dict(self._priorities))

    def _next_goal(self, agent: "Agent") -> Coordinates2D:
        """Input: the agent about to be (re-)tasked — unused, FCFS ignores
        identity.
        Output: the next goal position, popped from the front of
        goal_pool and pushed back at the end so the pool never empties.
        """
        goal = self._goal_pool.pop(0)
        self._goal_pool.append(goal)
        return goal
