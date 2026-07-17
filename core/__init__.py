"""Pure simulation engine — no rendering or algorithm dependencies."""

from .entities import Position, WorldEntity, Agent
from .environment import Grid
from .engine import (
    Coordinator, PlanResult, DispatchIntent,
    Dispatcher, StaticDispatcher, Simulation,
)

__all__ = [
    "Position", "WorldEntity", "Agent",
    "Grid", "Simulation",
    "Coordinator", "PlanResult", "DispatchIntent",
    "Dispatcher", "StaticDispatcher",
]
