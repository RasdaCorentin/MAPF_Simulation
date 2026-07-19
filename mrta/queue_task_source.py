from .task import Task
from .task_source import TaskSource


class QueueTaskSource(TaskSource):
    """Task source fed from the outside: a queue drained once per poll.

    The bridge between an interactive caller (a UI sending a batch of
    agents somewhere) and the dispatch loop. The caller pushes tasks
    whenever it likes; ``poll()`` hands over everything queued since the
    last cycle and empties the queue, so no task is ever delivered twice.

    Task ids are handed out by the source, which keeps the caller from
    having to track a counter and guarantees they stay unique.
    """

    def __init__(self) -> None:
        """Input: none.
        Output: None. Starts with an empty queue.
        """
        self._queue: list[Task] = []
        self._next_id = 0

    def push(self, task: Task) -> None:
        """Input: a task to deliver at the next poll.
        Output: None.
        """
        self._queue.append(task)

    def push_many(self, tasks: list[Task]) -> None:
        """Input: tasks to deliver at the next poll.
        Output: None.
        """
        self._queue.extend(tasks)

    def next_id(self) -> int:
        """Input: none.
        Output: a fresh unique task id.
        """
        task_id = self._next_id
        self._next_id += 1
        return task_id

    def poll(self, current_step: int) -> list[Task]:
        """Input: the current simulation step (unused — availability is
        decided by the caller, not by a schedule).
        Output: every task queued since the last poll; the queue is left
        empty.
        """
        drained, self._queue = self._queue, []
        return drained
