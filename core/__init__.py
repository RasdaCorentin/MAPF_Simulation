"""Pure simulation engine — no rendering or algorithm dependencies."""

from .entities import Coordinates2D, manhattan_distance, WorldEntity, Agent, NamedRegion
from .environment import Grid2D
from .engine import (
    PathPlanner, StepOutcome, AssignmentManifest,
    MissionOrchestrator, FixedGoalDispatcher, WorldEngine,
)

__all__ = [
    "Coordinates2D", "manhattan_distance", "WorldEntity", "Agent", "NamedRegion",
    "Grid2D", "WorldEngine",
    "PathPlanner", "StepOutcome", "AssignmentManifest",
    "MissionOrchestrator", "FixedGoalDispatcher",
]
