from .task import Mission
from .task_source import MissionSource


class CompositeMissionSource(MissionSource):
    """Merges several sources into one, fetched from in order.

    A TaskDrivenOrchestrator takes a single source, but work legitimately
    arrives from more than one place: an operator queueing a batch by
    hand *and* a generator producing background load. Composing them
    keeps that a property of the scenario rather than a special case
    inside TaskDrivenOrchestrator.
    """

    def __init__(self, *sources: MissionSource) -> None:
        """Input: the sources to merge, in fetch order.
        Output: None.
        """
        self.sources = list(sources)

    def fetch_new_missions(self, current_step: int) -> list[Mission]:
        """Input: the current simulation step.
        Output: the concatenation of every source's missions for this
        step.
        """
        tasks: list[Mission] = []
        for source in self.sources:
            tasks.extend(source.fetch_new_missions(current_step))
        return tasks
