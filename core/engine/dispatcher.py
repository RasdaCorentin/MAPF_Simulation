from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..environment.grid import Grid


class Dispatcher(ABC):
    """Pre-planning hook run by ``Simulation.step()`` before the coordinator plans.

    Given the world state at the current step, a dispatcher updates the
    shared coordinator's goals/priorities (task allocation being the typical
    use). Keeping this abstraction in ``core`` lets ``Simulation`` own the
    tick order (dispatch -> plan) without importing ``mrta`` — exactly like
    it depends on ``Coordinator`` rather than on a concrete algorithm.
    ``FleetManager`` is the concrete dispatcher.
    """

    @abstractmethod
    def dispatch(self, agents: list["Agent"], grid: "Grid", step: int) -> None:
        """Input: all simulated agents, the grid, and the current step.
        Output: None. Mutates the shared coordinator (goals/priorities)
        so that the plan computed right after reflects the latest state.
        """
        ...
