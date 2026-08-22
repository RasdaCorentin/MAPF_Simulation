from dataclasses import dataclass, field

from ..entities.position import Coordinates2D


@dataclass(frozen=True)
class AssignmentManifest:
    """Immutable, absolute allocation state requested for the current tick.

    Produced by a ``MissionOrchestrator`` and consumed by ``PathPlanner.plan()``.
    It carries the *complete* desired state every tick (not deltas), so
    the planner never has to remember allocation across ticks:

    - ``goals``      : agent_id -> target Coordinates2D;
    - ``priorities`` : agent_id -> allocation priority (float), optional
      per agent — a planner without priorities simply ignores it.

    Being frozen and agent_id-keyed, one manifest is an auditable record of
    exactly what allocation asked for, before the planner alters anything.
    """

    goals:      dict[int, Coordinates2D] = field(default_factory=dict)
    priorities: dict[int, float]         = field(default_factory=dict)
