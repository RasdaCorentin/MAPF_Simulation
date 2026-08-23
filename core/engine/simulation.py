from typing import Optional

from ..environment.grid import Grid2D
from ..entities.agent import Agent
from ..entities.position import Coordinates2D
from ..entities.entity import WorldEntity
from .coordinator import PathPlanner
from .dispatcher import MissionOrchestrator
from .dispatch_intent import AssignmentManifest
from .plan_result import StepOutcome


class WorldEngine:
    """Pure simulation engine — no rendering dependency.

    Owns the grid, the agents and the world entities, and advances the
    world one step at a time. A PathPlanner is mandatory:
    ``advance_time_step()`` always delegates movement planning to
    ``coordinator.plan()``. An optional MissionOrchestrator (e.g. a
    TaskDrivenOrchestrator) is run at the start of each step to produce
    this tick's ``AssignmentManifest`` (goals/priorities), which is
    passed to ``plan()`` — the planner is never mutated.
    """

    def __init__(
        self,
        grid: Grid2D,
        coordinator: PathPlanner,
        dispatcher: Optional[MissionOrchestrator] = None,
    ) -> None:
        """Input: the grid, the (mandatory) coordination strategy, and an
        optional mission orchestrator run before planning each step.
        Output: None.
        """
        self.grid = grid
        self.agents: list[Agent] = []
        self.entities: list[WorldEntity] = []
        self._pending: list[WorldEntity] = []
        self.current_step = 0
        self.coordinator = coordinator
        self.dispatcher = dispatcher
        self.last_intent = AssignmentManifest()

    def register_agent(self, agent: Agent) -> None:
        """Input: an agent (its position must be free and valid).
        Output: None. Places the agent on the grid and registers it.
        """
        self.grid.place(agent)
        self.agents.append(agent)

    def spawn_static_obstacle(self, entity: WorldEntity) -> None:
        """Input: a world entity (obstacle, ...).
        Output: None. Placed immediately, or deferred until its
        ``appear_at`` step is reached.
        """
        self.entities.append(entity)
        if entity.appear_at <= self.current_step:
            self.grid.place(entity)
        else:
            self._pending.append(entity)

    def _validate_plan(self, result: StepOutcome) -> None:
        """Input: the StepOutcome about to be applied.
        Output: None. Raises ValueError if the plan is not applicable —
        a target off the grid, onto an active blocking entity, or shared
        by two agents.

        Checked *before* any mutation rather than rolled back after one:
        the lift/place transaction cannot fail partially if failure is
        impossible. A rollback would have to restore both ``position``
        and grid placement, and could itself fail. Cost is O(n).
        """
        claimed: dict[Coordinates2D, int] = {}
        for agent in self.agents:
            target = result.positions.get(agent.agent_id, agent.position)
            who = type(self.coordinator).__name__

            # Cell uniqueness covers every agent: a mover must not target
            # a cell a stationary agent keeps.
            if target in claimed:
                raise ValueError(
                    f"{who} planned agents {claimed[target]} and "
                    f"{agent.agent_id} onto the same cell {target}."
                )
            claimed[target] = agent.agent_id

            # Bounds and blocking only concern agents that actually move:
            # an agent standing still is not entering anything. This also
            # keeps an obstacle spawning onto an occupied cell (appear_at)
            # from being reported as a planning error.
            if target == agent.position:
                continue

            if not self.grid.is_within_bounds(target):
                raise ValueError(
                    f"{who} planned agent {agent.agent_id} onto {target}, "
                    f"outside the {self.grid.width}x{self.grid.height} grid."
                )
            if any(
                e.blocks_movement and e.is_active
                for e in self.grid.entities_at(target)
                if not isinstance(e, Agent)
            ):
                raise ValueError(
                    f"{who} planned agent {agent.agent_id} onto {target}, "
                    f"which holds a blocking entity."
                )

    def advance_time_step(self) -> StepOutcome:
        """Input: none.
        Output: the StepOutcome of this step (returned so that clients can
        display planning diagnostics without depending on the algorithm).
        Advances the world by one step: spawn pending entities, assign
        missions (if a mission orchestrator is attached), plan, validate,
        then apply the moves.
        """
        self.current_step += 1

        # 1. Spawn pending entities whose appear_at step has been reached
        due = [e for e in self._pending if e.appear_at <= self.current_step]
        for entity in due:
            self.grid.place(entity)
            self._pending.remove(entity)

        # 2. Assign missions before planning: compute this tick's manifest
        # (absolute goals/priorities). An empty manifest if no orchestrator.
        if self.dispatcher is not None:
            intent = self.dispatcher.assign_missions(self.agents, self.grid, self.current_step)
        else:
            intent = AssignmentManifest()
        self.last_intent = intent

        # 3. Planner computes all next positions from the manifest
        result = self.coordinator.plan(self.agents, self.grid, intent)

        # 4. Reject an inapplicable plan before touching the grid, so the
        # lift/place transaction below can never fail halfway through and
        # leave agents off the grid.
        self._validate_plan(result)

        # 5. Lift phase: unindex moving agents from the grid first
        # so they do not artificially block each other
        moving_agents = []
        for agent in self.agents:
            target_pos = result.positions.get(agent.agent_id, agent.position)
            if target_pos != agent.position:
                moving_agents.append((agent, target_pos))
                self.grid.unindex(agent)  # agent leaves its current cell

        # 6. Place phase: apply movement and put agents back on the grid.
        # _validate_plan() guarantees every target is free, so place() cannot raise.
        for agent, target_pos in moving_agents:
            agent.move_to(target_pos)
            self.grid.place(agent)

        return result

    def __repr__(self) -> str:
        """Input: none. Output: short human-readable state summary."""
        return f"WorldEngine(grid={self.grid}, agents={len(self.agents)}, step={self.current_step})"
