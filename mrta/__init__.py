"""Multi-Robot Task Allocation: tasks, sources, allocation and dispatch.

Depends only on core (Agent, Grid, Position, Dispatcher, DispatchIntent) —
never on algo or client.
"""

from .task import Task, TaskState
from .task_source import TaskSource
from .allocator import Allocator
from .fleet_manager import FleetManager

__all__ = ["Task", "TaskState", "TaskSource", "Allocator", "FleetManager"]
