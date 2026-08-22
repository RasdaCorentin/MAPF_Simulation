from abc import ABC, abstractmethod

from .task import Mission


class MissionSource(ABC):
    """Strategy interface for producing new missions over time.

    Polled once per assignment cycle by TaskDrivenOrchestrator;
    implementations decide which new missions (if any) become available
    at the given simulation step (e.g. reading a schedule, a queue, or
    user input).
    """

    @abstractmethod
    def fetch_new_missions(self, current_step: int) -> list[Mission]:
        """Input: the current simulation step.
        Output: newly available missions at this step (possibly empty).
        """
        ...
