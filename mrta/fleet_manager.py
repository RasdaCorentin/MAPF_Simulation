from core import Agent, Grid, PriorityBasedCoordinator

from .task import Task, TaskState
from .task_source import TaskSource
from .allocator import Allocator


class FleetManager:
    """Control loop bridging task sources, allocation and coordination.

    Each dispatch cycle: complete finished tasks, poll for new ones,
    then allocate pending tasks to free agents and push the resulting
    goals/priorities onto the coordinator shared with the Simulation.
    """

    def __init__(
        self,
        source: TaskSource,
        allocator: Allocator,
        coordinator: PriorityBasedCoordinator,
    ) -> None:
        """Input: the task source, the allocation strategy and the
        priority-based coordinator shared with the Simulation.
        Output: None.
        """
        self.source = source
        self.allocator = allocator
        self.coordinator = coordinator
        self.tasks: list[Task] = []

    def dispatch(self, agents: list[Agent], grid: Grid, step: int) -> None:
        """Input: all simulated agents, the grid, and the current step.
        Output: None. Runs one control cycle: complete, intake, allocate.
        """
        self._complete(agents)
        self._intake(step)
        self._allocate(agents, grid)

    def set_priority(self, task_id: int, priority: float) -> None:
        """Input: a task id and its new priority.
        Output: None. Updates the task and, if it is already assigned,
        propagates the new priority to the coordinator immediately.
        """
        for task in self.tasks:
            if task.task_id == task_id:
                task.priority = priority
                if task.assignee is not None:
                    self.coordinator.set_priority(task.assignee, priority)
                return

    def _intake(self, step: int) -> None:
        """Input: the current simulation step.
        Output: None. Polls the task source and registers new tasks.
        """
        self.tasks.extend(self.source.poll(step))

    def _allocate(self, agents: list[Agent], grid: Grid) -> None:
        """Input: all simulated agents and the grid.
        Output: None. Matches pending tasks to free agents and pushes
        goals/priorities to the coordinator for each matched pair.
        """
        pending = [t for t in self.tasks if t.state is TaskState.PENDING]
        if not pending:
            return

        assigned_agent_ids = {
            t.assignee.agent_id for t in self.tasks
            if t.state is TaskState.ASSIGNED and t.assignee is not None
        }
        free = [a for a in agents if a.agent_id not in assigned_agent_ids]
        if not free:
            return

        matches = self.allocator.allocate(pending, free, grid)
        for task, agent in matches.items():
            task.state = TaskState.ASSIGNED
            task.assignee = agent
            self.coordinator.set_goal(agent, task.target)
            self.coordinator.set_priority(agent, task.priority)

    def _complete(self, agents: list[Agent]) -> None:
        """Input: all simulated agents.
        Output: None. Marks assigned tasks whose assignee has reached
        the target as DONE.
        """
        for task in self.tasks:
            if task.state is TaskState.ASSIGNED and task.assignee is not None:
                if task.assignee.position == task.target:
                    task.state = TaskState.DONE
