"""
Shared helper for building a throwaway Grid + cloned Agents from a
joint configuration, used by both PIBTPlusCoordinator (which wraps the
result in a scratch Simulation to drive several ticks) and
LaCAMCoordinator's low level (which only needs one constrained pass,
no Simulation at all). Not a public coordinator-facing name — private
to algo/coordination/.
"""

from __future__ import annotations

from core import Position, Agent, Grid


def build_scratch_grid(config: dict[int, Position], source_grid: Grid) -> tuple[Grid, dict[int, Agent]]:
    """Input: a joint configuration (agent_id -> Position) and the real
    grid to clone static entities (obstacles, zones) from.
    Output: a fresh Grid carrying those same static entities, and
    cloned Agents at `config`'s positions — **not yet placed** on the
    returned grid. Placement is the caller's job, deliberately: a
    caller driving a scratch Simulation must place agents via
    ``Simulation.add_agent`` (which both places *and* registers them —
    placing here first would double-place and raise), while a caller
    that only needs one static constrained-PIBT pass (no Simulation)
    can place them directly with ``grid.place``.

    Cloning rather than reusing the real Agent objects keeps every
    search/simulation step here from ever touching the live grid.
    """
    scratch_grid = Grid(source_grid.width, source_grid.height)
    for e in source_grid.get_all():
        if not isinstance(e, Agent):
            scratch_grid.place(e)
    scratch_agents = {aid: Agent(aid, pos) for aid, pos in config.items()}
    return scratch_grid, scratch_agents
