"""
PIBTCoordinator — Priority Inheritance with Backtracking
Okumura et al., 2022.

PIBT is split into focused classes: reservations live in
ReservationTable, priorities in PriorityManager. The recursive core
(_pibt / _h) receives `grid` as an argument instead of storing it, so
no per-step grid state lives on the coordinator.

Usage:
    a0 = Agent(0, Position(0, 0))
    a1 = Agent(1, Position(9, 9))
    pibt = PIBTCoordinator()
    pibt.set_goal(a0, Position(9, 9))
    pibt.set_goal(a1, Position(0, 0))
    pibt.set_priority(a0, 5.0)   # optional
    sim = Simulation(grid, coordinator=pibt)
    sim.add_agent(a0); sim.add_agent(a1)

plan() returns a PlanResult DTO carrying next positions plus PIBT
diagnostics (priority order, moves, priority inheritances).
"""

from __future__ import annotations

from typing import Optional

from core import Position, PriorityBasedCoordinator, Agent, Grid, PlanResult

from .reservation_table import ReservationTable
from .priority_manager import PriorityManager

DIRS    = [Position(0, -1), Position(0, 1), Position(-1, 0), Position(1, 0)]
EPSILON = 1e-3


class PIBTCoordinator(PriorityBasedCoordinator):
    """PIBT coordinator — implements the PriorityBasedCoordinator interface.

    Plugged into Simulation.coordinator, replaces per-agent movement
    computation with a single coordinated planning pass driven by agent
    priorities (Priority Inheritance with Backtracking).
    """

    def __init__(
        self,
        goals: Optional[dict[Agent, Position]] = None,
        initial_priorities: Optional[dict[Agent, float]] = None,
    ) -> None:
        """Input: optional initial goals (Agent -> target Position) and
        initial base priorities (Agent -> float; default: insertion
        index, last added = highest priority).
        Output: None.
        """
        self.goals: dict[Agent, Position] = goals.copy() if goals is not None else {}
        self._reservations = ReservationTable()
        self._priorities = PriorityManager(initial_priorities)
        self._processed: set[Agent] = set()
        self._inheritance: list[tuple[Agent, Agent]] = []

    # ── Coordinator interface ──────────────────────────────────────────────

    def set_goal(self, agent: Agent, target: Position) -> None:
        """Input: an agent and its new target cell.
        Output: None.
        """
        self.goals[agent] = target

    def set_priority(self, agent: Agent, priority: float) -> None:
        """Input: an agent and its new base priority.
        Output: None.
        """
        self._priorities.set_base(agent, priority)

    # ── Heuristic ────────────────────────────────────────────────────────────

    def _h(self, pos: Position, agent: Agent, grid: Grid) -> int:
        """Input: a candidate position, the agent it is evaluated for,
        and the grid.
        Output: Manhattan distance from pos to the agent's goal.
        """
        g = self.goals[agent]
        return abs(pos.x - g.x) + abs(pos.y - g.y)

    # ── Recursive PIBT algorithm (Algorithm 1) ───────────────────────────────

    def _pibt(self, agent: Agent, parent: Optional[Agent], grid: Grid) -> bool:
        """Input: the agent being placed, its pusher (None at top level),
        and the grid.
        Output: True if a valid next cell was reserved for the agent.
        """
        candidates: list[Position] = []
        for d in DIRS:
            v = agent.position + d
            if grid.is_valid(v) and not any(
                e.blocks_movement and e.active
                for e in grid.get_entities_at(v)
                if not isinstance(e, Agent)
            ):
                candidates.append(v)
        candidates.sort(key=lambda v: self._h(v, agent, grid))

        # An agent already at its goal prefers to stay in place
        if agent.position == self.goals.get(agent):
            candidates.insert(0, agent.position)

        if parent is not None:
            candidates = [v for v in candidates if v != parent.position]

        for v in candidates:
            # Staying in place: always valid if no other agent has reserved the cell
            if v == agent.position:
                reserving = self._reservations.get_reserving_agent(v)
                if reserving is None or reserving == agent:
                    self._reservations.reserve(agent, v)
                    return True
                continue

            reserving = self._reservations.get_reserving_agent(v)
            if reserving is not None and reserving != agent:
                continue

            occupant = grid.get_agent_at(v)

            # Anti-recursion guard: only recurse into an occupant if sigma(occupant)
            # is still undefined (occupant has not reserved a cell yet). An
            # occupant that already reserved a cell will free its current one.
            # Checking _processed here (updated only AFTER return) would
            # re-enter agents still on the call stack -> infinite recursion
            # on cycles (rotations).
            if occupant is not None and self._reservations.get_reservation(occupant) is None:
                self._reservations.reserve(agent, v)
                self._priorities.set_base(occupant, self._priorities.get_priority(agent) + EPSILON)
                if not self._pibt(occupant, agent, grid):
                    self._reservations.release(agent)
                    continue
                self._processed.add(occupant)
                self._inheritance.append((agent, occupant))
                return True

            if occupant is None or self._reservations.get_reservation(occupant) is not None:
                self._reservations.reserve(agent, v)
                return True

        self._reservations.reserve(agent, agent.position)
        return False

    # ── Interface Coordinator ─────────────────────────────────────────────────

    def plan(self, agents: list[Agent], grid: Grid) -> PlanResult:
        """Input: all simulated agents and the grid (read-only).
        Output: a PlanResult with next positions plus PIBT diagnostics
        (priority order, moves, priority inheritances, priorities).
        """
        self._priorities.update(agents)

        for agent in agents:
            if agent.position == self.goals.get(agent):
                self._priorities.set_base(agent, float("-inf"))

        self._reservations.clear()
        self._processed.clear()
        self._inheritance.clear()

        ordered = sorted(agents, key=lambda a: -self._priorities.get_priority(a))

        for agent in ordered:
            if agent not in self._processed:
                self._pibt(agent, None, grid)
                self._processed.add(agent)

        positions: dict[int, Position] = {}
        for a in agents:
            reservation = self._reservations.get_reservation(a)
            positions[a.agent_id] = reservation if reservation is not None else a.position

        return PlanResult(
            positions=positions,
            moves={a.agent_id: (a.position, positions[a.agent_id]) for a in agents},
            order=[a.agent_id for a in ordered],
            inheritance=[(p.agent_id, q.agent_id) for p, q in self._inheritance],
            priorities={a.agent_id: self._priorities.get_priority(a) for a in agents},
        )
