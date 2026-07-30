"""
pibt_core — the recursive PIBT pass (Algorithm 1), extracted so a caller
other than PIBTCoordinator can drive it against an externally-owned
ReservationTable/PriorityManager.

PIBTCoordinator.plan() clears its ReservationTable and rebuilds its
PriorityManager's dynamic priorities before every pass — the only
public injection points (ReservationTable.reserve, PriorityManager.set_base)
get wiped by that reset, so there is no way to pre-seed a fixed
reservation through PIBTCoordinator's own public surface and have it
survive. run_pibt_pass() does not reset anything itself: the caller
decides what is already reserved before the pass starts, which is what
lets a constrained caller (e.g. LaCAM's low level) fix one agent's next
cell and let the rest cascade around it.
"""

from __future__ import annotations

from typing import Optional

from core import Position, Agent, Grid

from .reservation_table import ReservationTable
from .priority_manager import PriorityManager

DIRS    = [Position(0, -1), Position(0, 1), Position(-1, 0), Position(1, 0)]
EPSILON = 1e-3


def _h(pos: Position, agent: Agent, goals: dict[Agent, Position]) -> int:
    """Input: a candidate position, the agent it is evaluated for, and
    the goals mapping.
    Output: Manhattan distance from pos to the agent's goal.
    """
    g = goals[agent]
    return abs(pos.x - g.x) + abs(pos.y - g.y)


def _pibt(
    agent: Agent,
    parent: Optional[Agent],
    grid: Grid,
    goals: dict[Agent, Position],
    priorities: PriorityManager,
    reservations: ReservationTable,
    inherited: dict[Agent, float],
    inheritance: list[tuple[Agent, Agent]],
    processed: set[Agent],
) -> bool:
    """Input: the agent being placed, its pusher (None at top level), the
    grid, the goals mapping, and the shared priority/reservation/processed
    state.
    Output: True if a valid next cell was reserved for the agent.

    Identical control flow to PIBTCoordinator._pibt — behaviour is not
    duplicated, only re-parameterized so it no longer reads `self`.

    `processed` is deliberately distinct from "has a reservation": a
    pushed agent that fails to move still ends up with a fallback
    reservation (stay in place, last line of this function) but is only
    added to `processed` on the *success* branch below. That is what
    lets run_pibt_pass's outer loop give a failed pushee a second,
    unconstrained top-level attempt instead of leaving it stranded.
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
    candidates.sort(key=lambda v: _h(v, agent, goals))

    # An agent already at its goal prefers to stay in place
    if agent.position == goals.get(agent):
        candidates.insert(0, agent.position)

    if parent is not None:
        candidates = [v for v in candidates if v != parent.position]

    for v in candidates:
        # Staying in place: always valid if no other agent has reserved the cell
        if v == agent.position:
            reserving = reservations.get_reserving_agent(v)
            if reserving is None or reserving == agent:
                reservations.reserve(agent, v)
                return True
            continue

        reserving = reservations.get_reserving_agent(v)
        if reserving is not None and reserving != agent:
            continue

        occupant = grid.get_agent_at(v)

        # Anti-recursion guard: only recurse into an occupant if sigma(occupant)
        # is still undefined (occupant has not reserved a cell yet).
        if occupant is not None and reservations.get_reservation(occupant) is None:
            reservations.reserve(agent, v)
            inherited.setdefault(occupant, priorities.get_base(occupant))
            priorities.set_base(occupant, priorities.get_priority(agent) + EPSILON)
            if not _pibt(occupant, agent, grid, goals, priorities, reservations, inherited, inheritance, processed):
                reservations.release(agent)
                continue
            processed.add(occupant)
            inheritance.append((agent, occupant))
            return True

        if occupant is None or reservations.get_reservation(occupant) is not None:
            reservations.reserve(agent, v)
            return True

    reservations.reserve(agent, agent.position)
    return False


def run_pibt_pass(
    grid: Grid,
    goals: dict[Agent, Position],
    priorities: PriorityManager,
    reservations: ReservationTable,
    order: list[Agent],
    processed: Optional[set[Agent]] = None,
) -> tuple[list[tuple[Agent, Agent]], dict[Agent, float]]:
    """Input: the grid, goals, the shared PriorityManager and
    ReservationTable, the priority order to process agents in, and an
    optional pre-seeded `processed` set.
    Output: (inheritance, inherited) — the (pusher, pushed) pairs this
    pass produced, and the pre-boost base priority of every agent it
    boosted.

    Does NOT clear `reservations` first, and deliberately does NOT undo
    the inheritance boosts before returning — both are the caller's
    responsibility. PIBTCoordinator reads `priorities.get_priority()`
    for its PlanResult diagnostics *before* undoing the boosts (the
    diagnostic reflects what this tick's cascade actually used), then
    undoes them; a caller that does not care about that ordering (e.g.
    LaCAM's low level, which throws its PriorityManager away right
    after) can simply ignore the returned `inherited` mapping.

    PIBTCoordinator clears `reservations` before calling and passes no
    `processed` (an unconstrained pass, starting empty like its own
    former `_processed`). A constrained caller (e.g. LaCAM's low level)
    instead pre-reserves one agent's cell and pre-seeds
    `processed={that_agent}`, so the outer loop below never gives it a
    top-level attempt and its fixed reservation survives the whole pass
    untouched.
    """
    inherited: dict[Agent, float] = {}
    inheritance: list[tuple[Agent, Agent]] = []
    processed = set() if processed is None else processed
    for agent in order:
        if agent not in processed:
            _pibt(agent, None, grid, goals, priorities, reservations, inherited, inheritance, processed)
            processed.add(agent)

    return inheritance, inherited
