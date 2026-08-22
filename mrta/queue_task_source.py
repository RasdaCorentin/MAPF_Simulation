from .task import Mission
from .task_source import MissionSource


class QueueMissionSource(MissionSource):
    """Mission source fed from the outside: a queue drained once per fetch.

    The bridge between an interactive caller (a UI sending a batch of
    agents somewhere) and the assignment loop. The caller pushes missions
    whenever it likes; ``fetch_new_missions()`` hands over everything
    queued since the last cycle and empties the queue, so no mission is
    ever delivered twice.

    Pushed missions need no meaningful ``task_id``: TaskDrivenOrchestrator
    stamps a unique one at intake, so several sources can coexist without
    numbering into each other.
    """

    def __init__(self) -> None:
        """Input: none.
        Output: None. Starts with an empty queue.
        """
        self._queue: list[Mission] = []

    def push(self, task: Mission) -> None:
        """Input: a mission to deliver at the next fetch.
        Output: None.
        """
        self._queue.append(task)

    def push_many(self, tasks: list[Mission]) -> None:
        """Input: missions to deliver at the next fetch.
        Output: None.
        """
        self._queue.extend(tasks)

    def fetch_new_missions(self, current_step: int) -> list[Mission]:
        """Input: the current simulation step (unused — availability is
        decided by the caller, not by a schedule).
        Output: every mission queued since the last fetch; the queue is
        left empty.
        """
        drained, self._queue = self._queue, []
        return drained
