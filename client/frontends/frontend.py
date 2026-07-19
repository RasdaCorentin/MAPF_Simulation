from abc import ABC, abstractmethod

from client.control import SimulationController


class Frontend(ABC):
    """Presentation strategy over a SimulationController.

    A frontend owns the clock and the output device; it never owns the
    simulation. ``SimulationController.step()`` stays a pure "advance by
    one", so pacing, buffering and interaction are entirely a frontend
    concern.
    """

    def __init__(self, controller: SimulationController) -> None:
        """Input: the controller to drive and display.
        Output: None.
        """
        self.controller = controller

    @abstractmethod
    def run(self, steps: int) -> None:
        """Input: how many steps to run (an upper bound; an interactive
        frontend may stop earlier).
        Output: None. Blocks until the frontend is done.
        """
        ...
