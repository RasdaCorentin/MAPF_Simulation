"""Multi-Robot Task Allocation: missions, sources, allocation and assignment.

Depends only on core (Agent, SpatialIndex, Coordinates2D, MissionOrchestrator,
AssignmentManifest) — never on algo or client.
"""

from .task import Mission, MissionState
from .task_source import MissionSource
from .queue_task_source import QueueMissionSource
from .random_task_source import RandomMissionSource
from .scripted_task_source import ScriptedMissionSource
from .composite_task_source import CompositeMissionSource
from .allocator import AssignmentStrategy
from .fleet_manager import TaskDrivenOrchestrator

__all__ = [
    "Mission", "MissionState", "MissionSource", "QueueMissionSource",
    "RandomMissionSource", "ScriptedMissionSource", "CompositeMissionSource",
    "AssignmentStrategy", "TaskDrivenOrchestrator",
]
