"""
PIBTPlusCoordinator — PIBT+ (Okumura et al.), batch, static goals only.

PIBT+ runs plain PIBT until it stalls, then hands the unresolved agents
to a Push-and-Swap complement solver to reach the exact goal
configuration. Both phases are *batch*: the whole joint path is solved
once, against a scratch Simulation, before any real tick executes; each
real ``plan()`` call afterwards just replays the next cached
configuration. See the root ``AGENT.md``'s "static-mode-only
limitation" note for why: this project's MRTA mode reassigns agent
goals continuously, and a joint batch path cannot survive that — one
agent's goal changing invalidates the whole path for every agent. This
coordinator only supports fixed goals for the run's lifetime
(``--mode static``); ``ScenarioConfig`` refuses any other combination,
and ``plan()`` itself raises if ``intent.goals`` ever changes anyway, as
a second guard for callers that bypass the config layer (the same way
``sim_many_pibt.py`` already does).

No closed-form T_min (the paper's bound on how long plain PIBT needs
before completing) is computed here — there is no graph-diameter
utility in this codebase to derive one from. It is replaced by a
stall/cap heuristic: phase 1 stops once no agent has improved its
Manhattan distance to goal for ``stall_patience`` consecutive ticks, or
after ``hard_cap`` ticks regardless. This is a documented deviation
from the paper's guarantee, not an oversight.
"""

from __future__ import annotations

from typing import Optional

from core import (
    Position, Coordinator, Agent, Grid, PlanResult, DispatchIntent,
    Simulation, StaticDispatcher,
)

from .pibt_coordinator import PIBTCoordinator
from .push_and_swap import PushAndSwapCoordinator
from ._scratch import build_scratch_grid

Config = dict[int, Position]


def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _build_scratch(agents: list[Agent], grid: Grid, dispatcher) -> Simulation:
    """Input: the real agents/grid, and a dispatcher for the scratch run.
    Output: a throwaway Simulation cloning that state.

    Uses add_agent() rather than placing clones directly: Simulation.agents
    is only populated through add_agent (which both places on the grid
    and appends to the list) — build_scratch_grid deliberately leaves
    its clones unplaced for exactly this reason.
    """
    config = {a.agent_id: a.position for a in agents}
    scratch_grid, clones = build_scratch_grid(config, grid)
    scratch_sim = Simulation(scratch_grid, coordinator=PIBTCoordinator(), dispatcher=dispatcher)
    for aid in config:
        scratch_sim.add_agent(clones[aid])
    return scratch_sim


class PIBTPlusCoordinator(Coordinator):
    """PIBT+ coordinator — implements the Coordinator interface.

    Batch algorithm: solves the whole joint path once (first ``plan()``
    call) then replays it. See module docstring for the static-goals
    scoping this implies.
    """

    def __init__(self, stall_patience: Optional[int] = None, hard_cap: Optional[int] = None) -> None:
        """Input: optional overrides for the T_min stand-in — ticks of
        no per-agent progress before phase 1 gives up (default derived
        from grid size), and a hard tick cap on phase 1 regardless.
        Output: None.
        """
        self._stall_patience = stall_patience
        self._hard_cap = hard_cap
        self._cached_path: Optional[list[Config]] = None
        self._cached_goal_key: Optional[tuple] = None
        self._cursor: int = 0

    def _goal_key(self, intent: DispatchIntent) -> tuple:
        return tuple(sorted(intent.goals.items()))

    def _run_pibt_phase(
        self, scratch_sim: Simulation, goals: dict[int, Position],
    ) -> tuple[list[Config], list[int]]:
        """Input: the scratch Simulation (already wired with a plain
        PIBTCoordinator and a StaticDispatcher for `goals`), and those
        goals.
        Output: (joint_path, remaining_agent_ids) — every joint
        configuration PIBT produced, and the agents still not at goal
        when the stall/cap heuristic ended the phase.
        """
        joint_path: list[Config] = []
        best_dist = {
            a.agent_id: _manhattan(a.position, goals.get(a.agent_id, a.position))
            for a in scratch_sim.agents
        }
        n = len(scratch_sim.agents)
        cap = self._hard_cap or 4 * (scratch_sim.grid.width + scratch_sim.grid.height) * max(n, 1)
        patience = self._stall_patience or 2 * (scratch_sim.grid.width + scratch_sim.grid.height)
        stalled_for = 0

        for _ in range(cap):
            result = scratch_sim.step()
            joint_path.append(dict(result.positions))

            if all(a.position == goals.get(a.agent_id, a.position) for a in scratch_sim.agents):
                return joint_path, []

            improved = False
            for a in scratch_sim.agents:
                d = _manhattan(a.position, goals.get(a.agent_id, a.position))
                if d < best_dist[a.agent_id]:
                    best_dist[a.agent_id] = d
                    improved = True
            stalled_for = 0 if improved else stalled_for + 1
            if stalled_for >= patience:
                break

        remaining = [
            a.agent_id for a in scratch_sim.agents
            if a.position != goals.get(a.agent_id, a.position)
        ]
        return joint_path, remaining

    def _solve(self, agents: list[Agent], grid: Grid, intent: DispatchIntent) -> list[Config]:
        """Input: the real agents/grid and this (fixed) tick's intent.
        Output: the whole joint path from the current configuration to
        the goal configuration, phase 1 (PIBT) followed by phase 2
        (Push-and-Swap) for whichever agents phase 1 left unresolved.
        """
        goals = dict(intent.goals)
        dispatcher = StaticDispatcher(goals=goals, priorities=dict(intent.priorities))
        scratch_sim = _build_scratch(agents, grid, dispatcher)

        joint_path, remaining = self._run_pibt_phase(scratch_sim, goals)
        if not remaining:
            return joint_path

        # Hand off: swap the coordinator on the same scratch Simulation
        # instance (a plain mutable attribute) and keep ticking it, so
        # phase 2 continues from exactly where phase 1 left off.
        scratch_sim.coordinator = PushAndSwapCoordinator(
            goals={aid: goals[aid] for aid in remaining}
        )
        second_cap = self._hard_cap or 4 * (scratch_sim.grid.width + scratch_sim.grid.height) * max(len(remaining), 1)
        for _ in range(second_cap):
            if all(
                a.position == goals.get(a.agent_id, a.position)
                for a in scratch_sim.agents if a.agent_id in remaining
            ):
                return joint_path
            result = scratch_sim.step()
            joint_path.append(dict(result.positions))

        raise RuntimeError(
            "PIBTPlusCoordinator: Push-and-Swap failed to converge within "
            f"{second_cap} steps for agents {remaining} — the instance may "
            "not be well-formed (this codebase does not validate that)."
        )

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
                "PIBTPlusCoordinator: intent.goals changed mid-run (agent "
                "goal churn). PIBT+ only supports --mode static with fixed "
                "goals; see algo/AGENT.md."
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
