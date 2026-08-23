from abc import ABC, abstractmethod

from core import Agent, Grid2D

from .task import Mission


class AssignmentStrategy(ABC):
    """Strategy interface for matching pending missions to free agents."""

    @abstractmethod
    def match_missions_to_units(
        self, pending: list[Mission], free: list[Agent], grid: Grid2D
    ) -> dict[Mission, Agent]:
        """Input: pending missions, free agents (no assigned mission), and
        the grid (read-only, e.g. for distance-aware strategies).
        Output: a dict mapping each matched Mission to its assigned Agent.
        Unmatched missions or agents are simply absent from the result.
        """
        ...
