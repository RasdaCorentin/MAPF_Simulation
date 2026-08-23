from typing import Optional, Type, TypeVar
from ..entities.position import Coordinates2D
from ..entities.entity import WorldEntity
from ..entities.agent import Agent

E = TypeVar("E", bound=WorldEntity)


class Grid2D:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._agents: dict[Coordinates2D, Agent] = {}
        self._static: dict[Coordinates2D, list[WorldEntity]] = {}

    def is_within_bounds(self, position: Coordinates2D) -> bool:
        return 0 <= position.x < self.width and 0 <= position.y < self.height

    def is_blocked(self, position: Coordinates2D) -> bool:
        """True if the cell contains an agent or an active blocking entity."""
        if position in self._agents:
            return True
        return any(
            e.blocks_movement and e.is_active
            for e in self._static.get(position, [])
        )

    def place(self, entity: WorldEntity) -> None:
        """Input: an entity.
        Output: None. Indexes it at its position.
        """
        if not self.is_within_bounds(entity.position):
            raise ValueError(f"Position {entity.position} out of bounds.")
        if isinstance(entity, Agent):
            if entity.position in self._agents:
                raise ValueError(f"Cell {entity.position} already occupied by an agent.")
            self._agents[entity.position] = entity
        else:
            self._static.setdefault(entity.position, []).append(entity)

    def unindex(self, entity: WorldEntity) -> None:
        if isinstance(entity, Agent):
            self._agents.pop(entity.position, None)
        else:
            bucket = self._static.get(entity.position, [])
            if entity in bucket:
                bucket.remove(entity)
            if not bucket:
                self._static.pop(entity.position, None)

    def agent_at(self, position: Coordinates2D) -> Optional[Agent]:
        return self._agents.get(position)

    def entities_at(self, position: Coordinates2D, kind: Optional[Type[E]] = None) -> list:
        agents = [self._agents[position]] if position in self._agents else []
        static = [e for e in self._static.get(position, []) if e.is_active]
        all_entities = agents + static
        if kind is not None:
            return [e for e in all_entities if isinstance(e, kind)]
        return all_entities

    def all_of_kind(self, kind: Optional[Type[E]] = None) -> list:
        """Input: an optional class to filter on.
        Output: every indexed entity.
        """
        static = [entity for bucket in self._static.values() for entity in bucket]
        all_entities = list(self._agents.values()) + static
        if kind is not None:
            return [e for e in all_entities if isinstance(e, kind)]
        return all_entities

    def __repr__(self) -> str:
        return f"Grid2D({self.width}x{self.height}, agents={len(self._agents)})"
