from typing import Iterable

from .entity import SpatialEntity
from .position import Coordinates2D


class NamedRegion(SpatialEntity):
    """A named region of the grid — "send the fleet to the loading station".

    A group of cells the operator addresses by name instead of by
    coordinates: loading station, working space, empty-rack area. Like
    any SpatialEntity it can spawn late (``appear_at``) and go inactive;
    unlike the others it covers several cells, so the grid indexes it at
    each of them rather than at a single corner. Asking "what is here?"
    anywhere inside a region therefore finds it.

    A named region never blocks movement: it labels ground, it does not
    occupy it. Robots cross it, park in it and work in it exactly as
    before, which is what lets it be added to a running scenario without
    touching the planner.

    It deliberately does **not** use ``SpatialEntity.scale``. ``scale`` is
    reserved and unimplemented; making it work would mean an agent
    *footprint*, forcing ``SpatialIndex``, ``is_blocked``,
    ``WorldEngine._validate_plan`` and PIBT's candidate generation to
    change together. ``cells`` is an explicit list and touches none of
    that.
    """

    def __init__(
        self,
        entity_id: int,
        name: str,
        cells: Iterable[Coordinates2D],
        appear_at: int = 0,
    ) -> None:
        """Input: unique id, the operator-facing name, the cells covered
        (at least one, duplicates dropped), and the spawn step.
        Output: None.
        """
        ordered = tuple(dict.fromkeys(cells))
        if not ordered:
            raise ValueError(f"NamedRegion {name!r} must cover at least one cell.")
        # The inherited ``position`` is a nominal anchor, kept so a
        # NamedRegion is a SpatialEntity like any other; ``cells`` is what
        # the grid indexes.
        super().__init__(entity_id, ordered[0], appear_at=appear_at, blocks_movement=False)
        self.name = name
        self._cells = ordered

    @property
    def cells(self) -> tuple:
        """Input: none.
        Output: the cells this region covers, in declaration order and
        without duplicates.
        """
        return self._cells

    def contains(self, position: Coordinates2D) -> bool:
        """Input: a position.
        Output: True if it falls inside this region.
        """
        return position in self._cells

    def __repr__(self) -> str:
        return f"NamedRegion({self.name!r}, {len(self._cells)} cells)"
