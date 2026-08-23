from dataclasses import dataclass, field

from ..entities.objective import Objective


@dataclass(frozen=True)
class AssignmentManifest:
    """Immutable, absolute allocation state requested for the current tick.

    Produced by a ``MissionOrchestrator`` and consumed by ``PathPlanner.plan()``.
    It carries the *complete* desired state every tick (not deltas), so
    the planner never has to remember allocation across ticks:

    - ``goals``      : every Objective wanted this tick, each already
      ``attach_to()``'d to the one Agent allowed to complete it;
    - ``priorities`` : agent_id -> allocation priority (float), optional
      per agent — a planner without priorities simply ignores it.

    Being frozen, one manifest is an auditable record of exactly what
    allocation asked for, before the planner alters anything.
    """

    goals:      list[Objective]  = field(default_factory=list)
    priorities: dict[int, float] = field(default_factory=dict)
