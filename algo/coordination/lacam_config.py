"""
Structures for LaCAMCoordinator's high-level DFS over joint
configurations. Kept separate from lacam_coordinator.py so the search
node shape can be read without the search/low-level machinery around it.
"""

from __future__ import annotations

from core import Position

Config = dict[int, Position]   # one joint configuration: agent_id -> Position


class HighLevelNode:
    """One node in LaCAM's DFS over joint configurations.

    `tried_constraints` records which (agent_id, forced-next-cell) pairs
    have already been expanded from this node, so the search can keep
    asking the same node for its *next* untried candidate across
    repeated visits instead of regenerating ones already explored.
    """

    def __init__(self, config: Config, parent: "HighLevelNode | None") -> None:
        self.config = config
        self.parent = parent
        self.tried_constraints: set[tuple[int, Position]] = set()


def is_goal_config(config: Config, goals: dict[int, Position]) -> bool:
    """Input: a joint configuration and the fixed goal for every agent.
    Output: True once every agent named in `goals` occupies it.
    """
    return all(config.get(aid) == goal for aid, goal in goals.items())


def config_key(config: Config) -> tuple:
    """Input: a joint configuration.
    Output: a hashable key for dedup in the search's `explored` set.
    """
    return tuple(sorted(config.items()))
