from typing import Optional, TYPE_CHECKING

from .entity import WorldEntity
from .position import Coordinates2D

if TYPE_CHECKING:
    from .agent import Agent


class Objective(WorldEntity):
    """A goal, not an obstacle.

    Placed and indexed like any WorldEntity — no special taxonomy needed.
    ``attach_to()`` is its only behavior: it binds this Objective to the
    one Agent allowed to complete it.
    """

    def __init__(self, entity_id: int, position: Coordinates2D, appear_at: int = 0) -> None:
        super().__init__(entity_id=entity_id, position=position, appear_at=appear_at)
        self._assignee: Optional["Agent"] = None

    @property
    def assignee(self) -> Optional["Agent"]:
        return self._assignee

    def attach_to(self, agent: "Agent") -> None:
        self._assignee = agent
