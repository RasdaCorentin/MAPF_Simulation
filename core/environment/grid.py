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
        Output: None. Indexes it at every cell it occupies.

        An entity is indexed at each of ``entity.cells`` — one cell for
        everything but a NamedRegion — so that asking "what is here?"
        anywhere inside a multi-cell entity finds it. Every cell is
        checked *before* any is written: a half-indexed region would be
        worse than a rejected one.
        """
        for cell in entity.cells:
            if not self.is_within_bounds(cell):
                raise ValueError(f"Position {cell} out of bounds.")
        if isinstance(entity, Agent):
            if entity.position in self._agents:
                raise ValueError(f"Cell {entity.position} already occupied by an agent.")
            self._agents[entity.position] = entity
        else:
            for cell in entity.cells:
                self._static.setdefault(cell, []).append(entity)

    def unindex(self, entity: WorldEntity) -> None:
        if isinstance(entity, Agent):
            self._agents.pop(entity.position, None)
        else:
            for cell in entity.cells:
                bucket = self._static.get(cell, [])
                if entity in bucket:
                    bucket.remove(entity)
                if not bucket:
                    self._static.pop(cell, None)

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
        Output: every indexed entity, each listed **once**.

        A multi-cell entity is indexed once per cell, so the raw buckets
        would yield a region as many times as it is wide. De-duplicating
        here rather than at each call site means the first caller who
        forgets cannot draw a region eight times or count it eight times.

        The key is object identity, not ``entity_id``: ids are unique
        per family (agents, obstacles and regions are each numbered from
        0), not across the grid, so keying on the id would silently drop
        an obstacle that happens to share a number with a region.
        """
        seen: set[int] = set()
        static = []
        for bucket in self._static.values():
            for entity in bucket:
                if id(entity) not in seen:
                    seen.add(id(entity))
                    static.append(entity)
        all_entities = list(self._agents.values()) + static
        if kind is not None:
            return [e for e in all_entities if isinstance(e, kind)]
        return all_entities

    def __repr__(self) -> str:
        return f"Grid2D({self.width}x{self.height}, agents={len(self._agents)})"
