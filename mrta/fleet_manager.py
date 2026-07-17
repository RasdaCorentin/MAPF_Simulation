from core import Agent, Grid, Position, DispatchIntent, Dispatcher

from .task import Task, TaskState
from .task_source import TaskSource
from .allocator import Allocator


class FleetManager(Dispatcher):
    """Control loop bridging task sources and allocation, as a Dispatcher.

    Pure with respect to the engine: ``dispatch()`` reads state, updates
    task assignments, and returns a ``DispatchIntent`` describing the
    complete goals/priorities of the active tasks — it never touches the
    coordinator. Each cycle completes finished tasks, polls for new ones,
    then allocates pending tasks to free agents.
    """

    def __init__(self, source: TaskSource, allocator: Allocator) -> None:
        """Input: the task source and the allocation strategy.
        Output: None.
        """
        self.source = source
        self.allocator = allocator
        self.tasks: list[Task] = []

    def dispatch(self, agents: list[Agent], grid: Grid, step: int) -> DispatchIntent:
        """Input: all simulated agents, the grid, and the current step.
        Output: the DispatchIntent (goals/priorities) for the active tasks
        after one cycle: complete -> intake -> allocate.
        """
        self._complete(agents)
        self._intake(step)
        self._allocate(agents, grid)
        return self._build_intent()

    def set_priority(self, task_id: int, priority: float) -> None:
        """Input: a task id and its new priority.
        Output: None. Updates the task; the new value reaches the
        coordinator through the next dispatch's intent.
        """
        for task in self.tasks:
            if task.task_id == task_id:
                task.priority = priority
                return

    def _intake(self, step: int) -> None:
        """Input: the current simulation step.
        Output: None. Polls the task source and registers new tasks.
        """
        self.tasks.extend(self.source.poll(step))

    def _allocate(self, agents: list[Agent], grid: Grid) -> None:
        """Input: all simulated agents and the grid.
        Output: None. Matches pending tasks to free agents (agents with no
        ASSIGNED task) via the allocator and records the assignments.
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

    def _complete(self, agents: list[Agent]) -> None:
        """Input: all simulated agents.
        Output: None. Marks assigned tasks whose assignee has reached the
        target as DONE.
        """
        for task in self.tasks:
            if task.state is TaskState.ASSIGNED and task.assignee is not None:
                if task.assignee.position == task.target:
                    task.state = TaskState.DONE

    def _build_intent(self) -> DispatchIntent:
        """Input: none.
        Output: a DispatchIntent with, for every ASSIGNED task, its
        assignee's goal and allocation priority.
        """
        goals: dict[int, Position] = {}
        priorities: dict[int, float] = {}
        for task in self.tasks:
            if task.state is TaskState.ASSIGNED and task.assignee is not None:
                aid = task.assignee.agent_id
                goals[aid] = task.target
                priorities[aid] = task.priority
        return DispatchIntent(goals=goals, priorities=priorities)
