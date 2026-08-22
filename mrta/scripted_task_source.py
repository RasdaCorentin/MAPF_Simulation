from .task import Mission
from .task_source import MissionSource


class ScriptedMissionSource(MissionSource):
    """Replays a fixed schedule of missions: ``{step: [Mission, ...]}``.

    The deterministic counterpart of RandomMissionSource. Because both
    the arrival times and the targets are fixed up front, a scenario
    built on it is fully reproducible — which is what makes it the
    natural basis for regression scenarios.
    """

    def __init__(self, schedule: dict[int, list[Mission]]) -> None:
        """Input: a mapping from simulation step to the missions that
        become available at that step.
        Output: None.
        """
        self._schedule = {step: list(tasks) for step, tasks in schedule.items()}

    def fetch_new_missions(self, current_step: int) -> list[Mission]:
        """Input: the current simulation step.
        Output: the missions scheduled for this step, each delivered once.
        """
        return self._schedule.pop(current_step, [])
