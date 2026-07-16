from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core import Agent, Position


class TaskState(Enum):
    """Lifecycle of a Task: waiting, assigned to an agent, or completed."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    DONE = "done"


@dataclass(eq=False)
class Task:
    """A unit of work to be carried out by some agent: reach `target`.

    Created by a TaskSource, matched to an agent by an Allocator, then
    tracked by FleetManager through PENDING -> ASSIGNED -> DONE.
    Hashable via ``task_id`` (immutable), so it can be used as a dict
    key in ``Allocator.allocate()`` results.
    """

    task_id: int
    target: Position
    priority: float = 0.0
    state: TaskState = TaskState.PENDING
    assignee: Optional[Agent] = None
    created_step: int = 0

    def __eq__(self, other: object) -> bool:
        """Input: another object. Output: equality based on task_id."""
        if not isinstance(other, Task):
            return NotImplemented
        return self.task_id == other.task_id

    def __hash__(self) -> int:
        """Input: none. Output: hash based on the immutable task_id."""
        return hash(self.task_id)
