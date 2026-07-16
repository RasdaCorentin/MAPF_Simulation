from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..entities.position import Position
    from ..environment.grid import Grid
    from .plan_result import PlanResult


class Coordinator(ABC):
    """Strategy interface for multi-agent coordination algorithms (MAPF).

    Receives the full list of agents and the grid, and returns a
    PlanResult describing the next position of every agent in a single
    coordinated pass. Plugged into Simulation via the ``coordinator``
    attribute.
    """

    @abstractmethod
    def plan(self, agents: list["Agent"], grid: "Grid") -> "PlanResult":
        """Input: all simulated agents and the grid (read-only).
        Output: a PlanResult with the next Position of every agent
        (``positions``/``moves`` filled; diagnostics optional).
        """
        ...

    def set_goal(self, agent: "Agent", target: "Position") -> None:
        """Input: an agent and its new target cell.
        Output: None. Default is a no-op — goal-less coordinators
        (e.g. random walk) simply ignore goals.
        """


class PriorityBasedCoordinator(Coordinator):
    """Coordinator refinement for algorithms driven by agent priorities.

    Interface segregation: ``set_priority`` lives here so that
    priority-less coordinators are not forced to implement it. The same
    instance is seen as a Coordinator by Simulation (plan/set_goal) and
    as a PriorityBasedCoordinator by FleetManager (set_priority).
    """

    @abstractmethod
    def set_priority(self, agent: "Agent", priority: float) -> None:
        """Input: an agent and its new base priority (higher = served first).
        Output: None.
        """
        ...
