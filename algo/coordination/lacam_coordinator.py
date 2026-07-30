"""
LaCAMCoordinator — LaCAM (Okumura), batch, static goals only.

Two-level search: the high level is a DFS over joint configurations
(HighLevelNode, one per visited configuration); the low level generates
one successor configuration at a time by fixing one agent's next cell
and letting a constrained PIBT pass resolve everyone else around that
choice. Like PIBTPlusCoordinator, the whole path is solved once against
a scratch grid — no Simulation is needed here, since a single low-level
call already produces one full joint move — and every real ``plan()``
call afterwards just replays the next cached configuration. See
``algo/AGENT.md``'s static-mode-only note and PIBTPlusCoordinator's
module docstring for why: this is a batch algorithm, incompatible with
this project's continuously-reassigned MRTA goals.

The low level reuses ``pibt_core.run_pibt_pass`` rather than
``PIBTCoordinator`` as a black box: PIBTCoordinator's own ``plan()``
clears its ReservationTable and rebuilds priorities before every call,
which would wipe a pre-seeded fixed reservation before it ever took
effect. ``run_pibt_pass`` leaves that entirely to the caller.
"""

from __future__ import annotations

from typing import Optional

from core import Position, Coordinator, Agent, Grid, PlanResult, DispatchIntent

from .pibt_core import run_pibt_pass, DIRS
from .reservation_table import ReservationTable
from .priority_manager import PriorityManager
from .lacam_config import Config, HighLevelNode, is_goal_config, config_key
from ._scratch import build_scratch_grid


def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


class LaCAMCoordinator(Coordinator):
    """LaCAM coordinator — implements the Coordinator interface.

    Batch algorithm: solves the whole joint path once (first ``plan()``
    call) then replays it. See module docstring for the static-goals
    scoping this implies.
    """

    def __init__(self, node_cap: int = 20000) -> None:
        """Input: a cap on how many high-level nodes the DFS may expand
        before giving up (an unsolvable or pathologically hard instance
        must not loop forever).
        Output: None.
        """
        self._node_cap = node_cap
        self._cached_path: Optional[list[Config]] = None
        self._cached_goal_key: Optional[tuple] = None
        self._cursor: int = 0

    def _goal_key(self, intent: DispatchIntent) -> tuple:
        return tuple(sorted(intent.goals.items()))

    # ── High level: DFS over joint configurations ───────────────────────────

    def _next_constraint(
        self, node: HighLevelNode, grid: Grid, goals: dict[int, Position],
    ) -> Optional[tuple[int, Position]]:
        """Input: the node to expand, the grid, and the goals.
        Output: an untried (agent_id, forced-next-cell) pair to branch
        on next from this node, or None once every candidate for its
        branching agent has been tried.

        The branching agent is whichever agent is currently furthest
        (Manhattan) from its own goal in this node's configuration —
        deterministic per node, so repeated calls keep branching on the
        same agent until its candidates are exhausted, matching
        `tried_constraints`'s bookkeeping.
        """
        branching_agent = max(
            goals, key=lambda aid: _manhattan(node.config[aid], goals.get(aid, node.config[aid]))
        )
        pos = node.config[branching_agent]
        candidates = [pos] + [pos + d for d in DIRS]
        candidates = [c for c in candidates if grid.is_valid(c)]
        candidates.sort(key=lambda c: _manhattan(c, goals.get(branching_agent, pos)))
        for c in candidates:
            if (branching_agent, c) not in node.tried_constraints:
                return (branching_agent, c)
        return None

    def _backtrack(self, node: HighLevelNode) -> list[Config]:
        """Input: the goal HighLevelNode.
        Output: the chronological list of configurations from the first
        future tick to the goal (the root's own config — the current,
        already-real state — is excluded).
        """
        configs: list[Config] = []
        while node.parent is not None:
            configs.append(node.config)
            node = node.parent
        configs.reverse()
        return configs

    def _solve(self, agents: list[Agent], grid: Grid, intent: DispatchIntent) -> list[Config]:
        """Input: the real agents/grid and this (fixed) tick's intent.
        Output: the whole joint path to the goal configuration, found
        by DFS.
        """
        goals = dict(intent.goals)
        root_config: Config = {a.agent_id: a.position for a in agents}
        root = HighLevelNode(root_config, parent=None)
        if is_goal_config(root_config, goals):
            return []

        stack = [root]
        explored = {config_key(root_config)}
        expansions = 0

        while stack:
            expansions += 1
            if expansions > self._node_cap:
                raise RuntimeError(
                    f"LaCAMCoordinator: search exceeded node_cap={self._node_cap} "
                    "without finding a solution."
                )
            node = stack[-1]
            constraint = self._next_constraint(node, grid, goals)
            if constraint is None:
                stack.pop()   # every candidate tried from here — backtrack
                continue
            node.tried_constraints.add(constraint)

            successor = self._generate_successor(node.config, grid, goals, constraint)
            if successor is None:
                continue   # infeasible under this constraint, try the next one

            key = config_key(successor)
            if key in explored:
                continue   # reached via a shorter/different path already
            explored.add(key)

            child = HighLevelNode(successor, parent=node)
            if is_goal_config(successor, goals):
                return self._backtrack(child)
            stack.append(child)

        raise RuntimeError(
            "LaCAMCoordinator: search space exhausted, no solution found "
            "(instance may not be well-formed)."
        )

    # ── Low level: one constrained PIBT pass ────────────────────────────────

    def _generate_successor(
        self, config: Config, grid: Grid, goals: dict[int, Position],
        fixed: tuple[int, Position],
    ) -> Optional[Config]:
        """Input: the configuration to branch from, the grid, the
        goals, and the (agent_id, forced-next-cell) constraint to
        respect.
        Output: the successor configuration, or None if the constraint
        is infeasible (the fixed cell is off-grid/blocked, or the
        agent it displaces cannot be resolved anywhere and clobbers the
        fixed reservation — see the guard below).

        A fresh Grid/ReservationTable/PriorityManager per call: each
        DFS branch must be independent, with no state leaking from a
        sibling branch already tried and abandoned.
        """
        fixed_id, fixed_cell = fixed
        if not grid.is_valid(fixed_cell) or any(
            e.blocks_movement and e.active
            for e in grid.get_entities_at(fixed_cell)
            if not isinstance(e, Agent)
        ):
            return None

        scratch_grid, clones = build_scratch_grid(config, grid)
        for a in clones.values():
            scratch_grid.place(a)

        order = list(clones.values())
        goals_by_agent = {a: goals.get(a.agent_id, a.position) for a in order}
        priorities = PriorityManager(
            initial_priorities={a: float(len(order) - i) for i, a in enumerate(order)}
        )
        reservations = ReservationTable()

        fixed_agent = clones[fixed_id]
        reservations.reserve(fixed_agent, fixed_cell)
        processed = {fixed_agent}

        run_pibt_pass(scratch_grid, goals_by_agent, priorities, reservations, order, processed=processed)

        # The agent displaced from `fixed_cell` may, if fully boxed in,
        # fall back to "stay in place" — which is exactly `fixed_cell`,
        # and ReservationTable.reserve() would silently overwrite the
        # pre-seeded entry. That agent was never part of the recursion
        # that would normally abandon and retry such a clobbered
        # reservation (fixed_agent sits outside the pass, already
        # `processed`), so detect it directly: the constraint is
        # infeasible if it did not survive the pass intact.
        if reservations.get_reservation(fixed_agent) != fixed_cell:
            return None

        successor: Config = {}
        for a in order:
            reservation = reservations.get_reservation(a)
            successor[a.agent_id] = reservation if reservation is not None else a.position
        return successor

    def plan(self, agents: list[Agent], grid: Grid, intent: DispatchIntent) -> PlanResult:
        """Input: all agents, the grid, and this tick's DispatchIntent.
        Output: the next cached joint configuration as a PlanResult.

        Solves the whole path on the first call; every later call must
        see the same goals (static mode only) or raises.
        """
        key = self._goal_key(intent)
        if self._cached_path is None:
            self._cached_path = self._solve(agents, grid, intent)
            self._cached_goal_key = key
            self._cursor = 0
        elif key != self._cached_goal_key:
            raise RuntimeError(
                "LaCAMCoordinator: intent.goals changed mid-run (agent goal "
                "churn). LaCAM only supports --mode static with fixed goals; "
                "see algo/AGENT.md."
            )

        if self._cursor < len(self._cached_path):
            target = self._cached_path[self._cursor]
            self._cursor += 1
        else:
            target = {a.agent_id: a.position for a in agents}   # goal reached, hold

        positions = {a.agent_id: target.get(a.agent_id, a.position) for a in agents}
        return PlanResult(
            positions=positions,
            moves={a.agent_id: (a.position, positions[a.agent_id]) for a in agents},
        )
