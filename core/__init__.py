"""Pure simulation engine — no rendering or algorithm dependencies."""

from .entities import Coordinates2D, manhattan_distance, SpatialEntity, Agent, NamedRegion
from .environment import SpatialIndex
from .engine import (
    PathPlanner, StepOutcome, AssignmentManifest,
    MissionOrchestrator, FixedGoalDispatcher, WorldEngine,
)

__all__ = [
    "Coordinates2D", "manhattan_distance", "SpatialEntity", "Agent", "NamedRegion",
    "SpatialIndex", "WorldEngine",
    "PathPlanner", "StepOutcome", "AssignmentManifest",
    "MissionOrchestrator", "FixedGoalDispatcher",
]
