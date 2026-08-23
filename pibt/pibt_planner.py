"""
PIBTPlanner — Priority Inheritance with Backtracking
Okumura et al., 2022.

PIBT is split into focused classes: reservations live in
ReservationTable, priorities in PriorityManager, and the recursive core
(Algorithm 1) lives in pibt_core.run_pibt_pass — shared with LaCAM's
low level, which needs to pre-seed a fixed reservation before a pass
and have it survive. PIBTPlanner itself is a thin per-tick wrapper:
goal/priority bookkeeping plus one unconstrained call into the shared
core.

Goals and base priorities are read from the tick's AssignmentManifest
(passed to plan()) — one Objective per agent, each already attach_to()'d
to the Agent it is for — never set by external mutation. The planner is
stateless about allocation but keeps its own navigation state across
ticks (dynamic priority drift, reservations).

Whether an agent parked on its goal stays demoted once it leaves is a
goal_reached_policy the caller chooses at construction — see
GoalReachedPolicy — because only the caller knows whether goals ever
move again.

Usage: see pibt/demo_one_shot.py, which wires PIBTPlanner behind a
one-shot MissionOrchestrator (goals fixed for the whole run).

plan() returns a StepOutcome DTO carrying next positions plus PIBT
diagnostics (priority order, moves, priority inheritances).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from core import Coordinates2D, Orientation, PathPlanner, Agent, Grid2D, StepOutcome, AssignmentManifest

from .reservation_table import ReservationTable
from .priority_manager import PriorityManager
from .pibt_core import run_pibt_pass, ORIENTATION_BY_DELTA


class GoalReachedPolicy(Enum):
    """How the goal-reached ``-inf`` demotion is undone, if ever.

    An agent standing on its goal is demoted to base priority ``-inf`` so
    it never contests a cell it does not need — see ``plan()``. Whether
    that demotion is later undone is *not* something ``PIBTPlanner``
    can decide on its own: it depends on whether goals ever move again,
    and only the caller that owns the goal regime (the
    ``MissionOrchestrator``, or the scenario built around it) knows
    that. Booking in one answer would make the planner silently wrong
    in whichever regime it did not anticipate, so the policy is
    threaded in at construction instead.

    TRANSIENT
        The demotion is a *state*, undone the instant it stops holding —
        the goal moved, or priority inheritance pushed the agent off it.
        Mandatory under a rotating-goal regime (MRTA / lifelong,
        ``FleetManager``): an agent that just finished a task must be
        able to contest a cell again to start the next one, or it could
        never move again after its first arrival. This is the default —
        it is the only policy safe under *every* regime, so a caller
        that does not know which regime it is in should not silently
        strand agents.

    PERMANENT
        The demotion is a one-way write, never undone — the historical
        behaviour, before the demotion became reversible. Under a
        *static* goal regime (``OneShotGoalDispatcher``, goals fixed for
        the run) this is measurably the better heuristic: on a 5x5 grid, 30
        seeds, static goals, it matches TRANSIENT up to 0.20 occupancy
        and pulls ahead by up to +0.17 success rate at maximum
        occupancy. An agent that has arrived and will never be asked to
        move again is better modelled as a soft, displaceable obstacle
        than as a contender that keeps re-entering the ranking — arrived
        agents stop contesting cells, and congestion trends down over
        the run instead of staying flat.
    """

    TRANSIENT = "transient"
    PERMANENT = "permanent"


class PIBTPlanner(PathPlanner):
    """PIBT planner — implements the PathPlanner interface.

    Plugged into WorldEngine.planner, replaces per-agent movement
    computation with a single coordinated planning pass driven by agent
    priorities (Priority Inheritance with Backtracking).
    """

    def __init__(
        self,
        goal_reached_policy: GoalReachedPolicy = GoalReachedPolicy.TRANSIENT,
        orientation: bool = False,
    ) -> None:
        """Input: goal_reached_policy — whether the goal-reached -inf
        demotion is undone once the agent leaves its goal (TRANSIENT,
        the default) or never (PERMANENT). See GoalReachedPolicy for
        which goal regime calls for which.
        orientation — whether plan() also fills StepOutcome.orientations,
        one heading per moving agent derived from its move direction (see
        ORIENTATION_BY_DELTA in pibt_core.py). Cosmetic only: it does not
        feed back into candidate selection, costs nothing, and does not
        enforce a rotate-XOR-move constraint — an agent can move and
        "face" its new direction in the same tick. Off by default.
        Output: None. Goals/priorities arrive per tick via the intent.
        """
        self.goals: dict[Agent, Coordinates2D] = {}
        self._reservations = ReservationTable()
        self._priorities = PriorityManager()
        self._goal_reached_policy = goal_reached_policy
        self._emit_orientation = orientation
        # Last (goal, priority) seen per agent_id — used to re-seed the base
        # priority ONLY when the allocation intent actually changes, so the
        # dynamic priority drift (anti-starvation) is never clobbered.
        self._last_intent: dict[int, tuple[Optional[Coordinates2D], Optional[float]]] = {}
        # Base priority overwritten by the goal-reached -inf demotion, kept so
        # the demotion can be undone when the agent is no longer at its goal
        # (TRANSIENT policy only — PERMANENT leaves it demoted, see
        # GoalReachedPolicy).
        self._demoted: dict[Agent, float] = {}

    # ── Interface PathPlanner ─────────────────────────────────────────────────

    def _apply_intent(self, agents: list[Agent], intent: AssignmentManifest) -> None:
        """Input: the agents and this tick's intent.
        Output: None. Rebuilds ``self.goals`` (fallback: stay in place) and
        re-seeds a base priority ONLY when an agent's goal changed or its
        business priority is strictly different from the previous tick —
        never otherwise, to preserve the dynamic priority drift.
        """
        # intent.goals is a list of Objectives, each attach_to()'d to the one
        # Agent it is for — flatten to agent_id -> Coordinates2D once, the
        # shape the rest of this planner (unchanged since before Objective)
        # already works with. An Objective without an assignee names no
        # agent and is skipped.
        goal_by_agent_id = {
            objective.assignee.agent_id: objective.position
            for objective in intent.goals
            if objective.assignee is not None
        }
        self.goals = {a: goal_by_agent_id.get(a.agent_id, a.position) for a in agents}

        for agent in agents:
            aid = agent.agent_id
            prio = intent.priorities.get(aid)
            if prio is None:
                continue
            key = (goal_by_agent_id.get(aid), prio)
            if self._last_intent.get(aid) != key:
                self._priorities.set_base(agent, prio)
                # A freshly seeded base wins over any pending restore.
                self._demoted.pop(agent, None)
            self._last_intent[aid] = key

    def plan(self, agents: list[Agent], grid: Grid2D, intent: AssignmentManifest) -> StepOutcome:
        """Input: all simulated agents, the grid (read-only), and this
        tick's AssignmentManifest (goals + optional priorities).
        Output: a StepOutcome with next positions plus PIBT diagnostics
        (priority order, moves, priority inheritances, priorities).
        """
        # Seed goals + base priorities from the intent BEFORE decaying, so a
        # freshly-seeded base is decayed once this tick like every other.
        self._apply_intent(agents, intent)

        self._priorities.update(agents)

        # "At its goal" is a *state*; under GoalReachedPolicy.TRANSIENT the
        # -inf demotion it triggers is undone as soon as the state stops
        # holding — the goal moved, or the agent was pushed off it by
        # priority inheritance. Writing -inf into the base without ever
        # restoring it strands the agent at the bottom of the ranking for
        # the rest of the run — which is exactly what PERMANENT asks for.
        for agent in agents:
            if agent.position == self.goals.get(agent):
                if agent not in self._demoted:
                    self._demoted[agent] = self._priorities.get_base(agent)
                    self._priorities.set_base(agent, float("-inf"))
            elif agent in self._demoted and self._goal_reached_policy is GoalReachedPolicy.TRANSIENT:
                self._priorities.set_base(agent, self._demoted.pop(agent))

        self._reservations.clear()

        ordered = sorted(agents, key=lambda a: -self._priorities.get_priority(a))

        inheritance, inherited = run_pibt_pass(
            grid, self.goals, self._priorities, self._reservations, ordered,
        )

        positions: dict[int, Coordinates2D] = {}
        for a in agents:
            reservation = self._reservations.get_reservation(a)
            positions[a.agent_id] = reservation if reservation is not None else a.position

        # An agent that does not move is simply absent here, same convention
        # as StepOutcome.positions — it keeps its current heading.
        orientations: dict[int, Orientation] = {}
        if self._emit_orientation:
            for a in agents:
                next_pos = positions[a.agent_id]
                delta = Coordinates2D(next_pos.x - a.position.x, next_pos.y - a.position.y)
                heading = ORIENTATION_BY_DELTA.get(delta)
                if heading is not None:
                    orientations[a.agent_id] = heading

        result = StepOutcome(
            positions=positions,
            moves={a.agent_id: (a.position, positions[a.agent_id]) for a in agents},
            order=[a.agent_id for a in ordered],
            inheritance=[(p.agent_id, q.agent_id) for p, q in inheritance],
            priorities={a.agent_id: self._priorities.get_priority(a) for a in agents},
            orientations=orientations,
        )

        # Inheritance boosts are scoped to this tick's cascade: undo them now
        # so an agent pushed once does not keep outranking its pusher forever.
        for agent, base in inherited.items():
            self._priorities.set_base(agent, base)

        return result
