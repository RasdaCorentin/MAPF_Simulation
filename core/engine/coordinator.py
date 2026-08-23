from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..environment.grid import Grid2D
    from .dispatch_intent import AssignmentManifest
    from .plan_result import StepOutcome


class PathPlanner(ABC):
    """Strategy interface for multi-agent coordination algorithms (MAPF).

    Receives the full list of agents, the grid, and the tick's
    ``AssignmentManifest`` (goals + optional priorities), and returns a
    ``StepOutcome`` with the next position of every agent in a single
    coordinated pass. The manifest is the *only* channel for goals and
    priorities — there is no external mutation of the planner, so the
    allocation layer and the navigation layer stay decoupled.
    Plugged into WorldEngine via the ``planner`` attribute.
    """

    @abstractmethod
    def plan(
        self,
        agents: list["Agent"],
        grid: "Grid2D",
        intent: "AssignmentManifest",
    ) -> "StepOutcome":
        """Input: all simulated agents, the grid (read-only), and this
        tick's AssignmentManifest (goals + optional priorities).
        Output: a StepOutcome with the next Coordinates2D of every agent
        (``positions``/``moves`` filled; diagnostics optional). A
        priority-less planner simply ignores ``intent.priorities``.
        """
        ...
