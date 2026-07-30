"""
PushAndSwapCoordinator — Luna & Bekris' Push-and-Swap, scoped down.

Solves agents one at a time (nearest-goal-first), each along its BFS
shortest path; an agent blocking the mover's next cell is relocated
first ("push"). Only ever run as PIBTPlusCoordinator's phase-2
complement solver against a scratch Simulation — never plugged into a
real one directly, so its goals come from the constructor, not from
DispatchIntent.

Two deliberate simplifications versus the textbook algorithm, both
consequences of targeting this project's engine and use case rather
than a general solver:

- **No tree-structured swap gadget.** The original algorithm's "swap"
  operation temporarily parks two agents through a branch node to pass
  each other in a corridor with no other free cell. Here, a push that
  cannot resolve within one tick (the whole blocking chain is boxed in)
  instead falls back to relocating the *closest* blocker to the nearest
  reachable free cell via BFS, one hop per tick, while the mover waits
  — a single-target relocation rather than a general bypass tree. This
  covers the practical corridor case (there usually is a nearby free
  cell somewhere) without the extra machinery a fully general swap
  needs; it does not cover an instance with literally no reachable free
  cell anywhere, which raises instead (see the well-formedness note
  below).
- **No vertex-swap.** This engine's ``Simulation.step()`` lifts every
  mover before placing any of them, so a direct two-agent position
  exchange would not actually collide — but ``PIBTCoordinator._pibt``
  never produces one anyway (a pushed agent may never step onto its
  pusher's own cell, ``parent.position`` is excluded from its
  candidates). Push-and-Swap keeps the same convention here for
  consistency across the coordinators this project ships.

**A known, verified failure mode, not just an abstract caveat**: the
mover being solved (`current`) is always required to advance into its
next cell *this tick* — only the *blocker* is ever a candidate for
relocation, `current` never waits or retreats. If phase 1 (plain PIBT)
happens to stall with a blocker fully cornered (a degree-1 cell, e.g. a
dead-end corridor end) and its one and only neighbor is exactly
`current`'s own cell, there is no free cell to relocate the blocker to
regardless of how much free space exists elsewhere in the grid — the
one thing that would resolve it (`current` retreating so the blocker
can pass) is exactly what this design never attempts. Confirmed
directly: a plain N-cell dead-end corridor with two agents needing a
full end-to-end swap can land in exactly this configuration and raise,
even though the instance is solvable (`LaCAMCoordinator` resolves the
same scenario by having one agent retreat fully to its own start before
the other advances — its DFS is not committed to one fixed solving
order the way this one-agent-at-a-time heuristic is). Prefer
``LaCAMCoordinator`` over PIBT+ for corridor-heavy layouts if this
matters; extending Push-and-Swap to let `current` yield is the natural
next step but is real additional machinery, not attempted here.

**Well-formedness is not validated** beyond the above. The classical
completeness guarantees assume a "well-formed" instance (every agent's
goal is reachable and there is always at least one cell free to shuffle
into). This grid is not checked for that up front; an instance without
a resolution raises ``RuntimeError`` rather than looping forever, and
the caller (``PIBTPlusCoordinator``) is expected to cap it externally
too.
"""

from __future__ import annotations

from collections import deque
from typing import Optional

from core import Position, Coordinator, Agent, Grid, PlanResult, DispatchIntent

DIRS = [Position(0, -1), Position(0, 1), Position(-1, 0), Position(1, 0)]


def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _passable(pos: Position, grid: Grid) -> bool:
    """A cell an agent could physically stand on: on the grid and not
    held by an active blocking (non-agent) entity. Whether another
    *agent* is there is a separate, tick-scoped question handled by the
    caller, not this static check.
    """
    return grid.is_valid(pos) and not any(
        e.blocks_movement and e.active
        for e in grid.get_entities_at(pos)
        if not isinstance(e, Agent)
    )


class PushAndSwapCoordinator(Coordinator):
    """Complement solver for PIBT+'s phase 2. Goals are fixed at
    construction — ``intent`` is ignored, exactly like ``StaticDispatcher``
    is ignored by nothing else in this codebase but here by design: this
    coordinator is never driven by a real dispatcher.
    """

    def __init__(self, goals: dict[int, Position], max_push_depth: int = 12) -> None:
        """Input: fixed goals (agent_id -> Position) and a cap on how
        deep a single-tick push cascade may recurse before giving up on
        it (in favour of the multi-tick relocation fallback).
        Output: None.
        """
        self._goals = dict(goals)
        self._solved: set[int] = set()
        self._order: Optional[list[int]] = None
        self._max_push_depth = max_push_depth
        # An in-progress multi-tick blocker relocation: {agent_id, path, cursor}.
        # Only ever one at a time — the mover it is clearing a path for waits.
        self._relocation: Optional[dict] = None

    # ── Search ───────────────────────────────────────────────────────────────

    def _bfs(
        self, start: Position, grid: Grid, blocked: set[Position],
        goal: Optional[Position] = None, avoid_targets: Optional[set[Position]] = None,
    ) -> Optional[list[Position]]:
        """Input: a start cell, the grid, cells that are permanently
        impassable (solved agents' final positions), and either a
        specific goal or (if goal is None) a request to find the
        nearest cell not in `avoid_targets`.
        Output: the path from start to the target, inclusive, or None
        if unreachable. Cells held by not-yet-solved agents are treated
        as passable — they are candidates to push aside, not obstacles.
        """
        if goal is not None and start == goal:
            return [start]
        avoid_targets = avoid_targets or set()
        visited = {start}
        queue = deque([[start]])
        while queue:
            path = queue.popleft()
            here = path[-1]
            for d in DIRS:
                nxt = here + d
                if nxt in visited or nxt in blocked or not _passable(nxt, grid):
                    continue
                next_path = path + [nxt]
                if goal is not None:
                    if nxt == goal:
                        return next_path
                elif nxt not in avoid_targets:
                    return next_path
                visited.add(nxt)
                queue.append(next_path)
        return None

    # ── Push (single-tick chain relocation) ─────────────────────────────────

    def _try_push(
        self, blocker_id: int, positions: dict[int, Position], grid: Grid,
        blocked: set[Position], forbidden: set[Position], depth: int = 0,
    ) -> bool:
        """Input: the agent to relocate, the tentative positions map for
        this tick (mutated in place on success), cells frozen by solved
        agents, cells no candidate target may land on (the pushing
        chain's own current cells — the no-vertex-swap rule), and the
        current recursion depth.
        Output: True if `blocker_id` (and transitively, whoever blocked
        it) was given a free adjacent cell this tick.
        """
        if depth > self._max_push_depth:
            return False
        pos_to_agent = {p: aid for aid, p in positions.items()}
        here = positions[blocker_id]
        for d in DIRS:
            v = here + d
            if v in forbidden or v in blocked or not _passable(v, grid):
                continue
            occupant_id = pos_to_agent.get(v)
            if occupant_id is None:
                positions[blocker_id] = v
                return True
            if occupant_id not in self._solved and self._try_push(
                occupant_id, positions, grid, blocked, forbidden | {here}, depth + 1
            ):
                positions[blocker_id] = v
                return True
        return False

    # ── Interface Coordinator ───────────────────────────────────────────────

    def plan(self, agents: list[Agent], grid: Grid, intent: DispatchIntent) -> PlanResult:
        """Input: all agents, the grid, and the tick's intent (ignored —
        goals are fixed at construction).
        Output: a PlanResult advancing the push/swap schedule by one tick.
        """
        by_id = {a.agent_id: a for a in agents}
        if self._order is None:
            # Only agents this coordinator was actually given a goal for —
            # `agents` is the *whole* scratch simulation, which also
            # includes agents PIBTPlusCoordinator's phase 1 already solved
            # and handed off unmoved; those are permanent obstacles here,
            # never candidates to move or push (see `blocked` below).
            self._order = sorted(
                (aid for aid in self._goals if aid in by_id),
                key=lambda aid: _manhattan(by_id[aid].position, self._goals[aid]),
            )

        positions: dict[int, Position] = {aid: a.position for aid, a in by_id.items()}

        for aid in self._goals:
            if aid in by_id and by_id[aid].position == self._goals[aid]:
                self._solved.add(aid)

        not_owned = {a.position for aid, a in by_id.items() if aid not in self._goals}
        blocked = not_owned | {by_id[aid].position for aid in self._solved if aid in by_id}

        if self._relocation is not None:
            positions = self._advance_relocation(positions)
            return self._result(agents, positions)

        current_id = next((aid for aid in self._order if aid not in self._solved), None)
        if current_id is None:
            return self._result(agents, positions)   # every agent solved — hold

        current = by_id[current_id]
        goal = self._goals[current_id]
        path = self._bfs(current.position, grid, blocked, goal=goal)
        if not path or len(path) < 2:
            raise RuntimeError(
                f"PushAndSwapCoordinator: no path for agent {current_id} "
                f"from {current.position} to {goal}."
            )
        next_cell = path[1]

        pos_to_agent = {p: aid for aid, p in positions.items()}
        blocker_id = pos_to_agent.get(next_cell)
        if blocker_id is None:
            positions[current_id] = next_cell
            return self._result(agents, positions)

        # `next_cell` is claimed by `current` below — forbidden from the
        # start, or a deeper link in the cascade could legally move back
        # into it once blocker_id vacates it, colliding with `current`.
        if self._try_push(blocker_id, positions, grid, blocked, forbidden={current.position, next_cell}):
            positions[current_id] = next_cell
            return self._result(agents, positions)

        # Push cascade fully boxed in: fall back to a multi-tick relocation
        # of the blocker to the nearest reachable free cell, one hop per
        # tick, while `current` waits this tick (this project's stand-in
        # for the textbook swap gadget — see module docstring).
        #
        # Every hop of this path must be *genuinely* free, not merely
        # "pushable" like `_bfs`'s ordinary treatment of agent-occupied
        # cells (correct for `current`'s primary path, where `_try_push`
        # actually clears each one): this relocation walks its path one
        # hop per tick with no pushing at all, and every other agent sits
        # frozen in place for that whole window (the early-return branch
        # above never lets anyone else move while a relocation is
        # active) — so a path through even a stationary, uninvolved
        # agent's cell would collide with it the moment that hop is taken.
        occupied = set(positions.values()) - {positions[blocker_id]}
        reloc_path = self._bfs(
            positions[blocker_id], grid, blocked | occupied,
            avoid_targets=set(),
        )
        if not reloc_path or len(reloc_path) < 2:
            raise RuntimeError(
                f"PushAndSwapCoordinator: agent {current_id} blocked by "
                f"{blocker_id}, no reachable free cell to relocate it to "
                f"(instance may not be well-formed)."
            )
        self._relocation = {"agent_id": blocker_id, "path": reloc_path, "cursor": 0}
        positions = self._advance_relocation(positions)
        return self._result(agents, positions)

    def _advance_relocation(self, positions: dict[int, Position]) -> dict[int, Position]:
        """Input: this tick's tentative positions.
        Output: the same dict, with the in-progress relocation's next
        hop applied; clears `self._relocation` once its path is spent.
        """
        reloc = self._relocation
        reloc["cursor"] += 1
        positions[reloc["agent_id"]] = reloc["path"][reloc["cursor"]]
        if reloc["cursor"] >= len(reloc["path"]) - 1:
            self._relocation = None
        return positions

    def _result(self, agents: list[Agent], positions: dict[int, Position]) -> PlanResult:
        return PlanResult(
            positions=positions,
            moves={a.agent_id: (a.position, positions[a.agent_id]) for a in agents},
        )
