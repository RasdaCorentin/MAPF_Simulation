import random
from typing import Optional

from core import SpatialIndex, Coordinates2D

from .task import Mission
from .task_source import MissionSource


class RandomMissionSource(MissionSource):
    """Emits random missions on free cells, at a fixed rate.

    Drives autonomous runs (benchmarks, demos with no operator) where
    the fleet should stay busy without anyone clicking. Seeded through
    ``random.Random`` so a run is reproducible from its seed alone.

    The grid is captured at construction: the source needs it to pick a
    free target, and a MissionSource is fetched from with the step only.
    """

    def __init__(
        self,
        grid: SpatialIndex,
        every: int = 5,
        count: int = 1,
        seed: Optional[int] = None,
    ) -> None:
        """Input: the grid to sample targets from, the period in steps
        between emissions, how many missions per emission, and the RNG
        seed.
        Output: None.
        """
        self._grid = grid
        self._every = max(1, every)
        self._count = count
        self._rng = random.Random(seed)

    def fetch_new_missions(self, current_step: int) -> list[Mission]:
        """Input: the current simulation step.
        Output: ``count`` missions on distinct free cells every ``every``
        steps, an empty list otherwise.
        """
        if current_step % self._every != 0:
            return []

        free = [
            Coordinates2D(x, y)
            for x in range(self._grid.width)
            for y in range(self._grid.height)
            if not self._grid.is_blocked(Coordinates2D(x, y))
        ]
        if not free:
            return []

        targets = self._rng.sample(free, min(self._count, len(free)))
        return [
            # task_id is a placeholder: TaskDrivenOrchestrator stamps a
            # unique one at intake, so sources never number into each
            # other.
            Mission(task_id=0, target=target, created_step=current_step,
                    last_improvement_step=current_step)
            for target in targets
        ]
