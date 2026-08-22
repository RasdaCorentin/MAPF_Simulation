from dataclasses import dataclass, field

from ..entities.position import Coordinates2D


@dataclass(frozen=True)
class StepOutcome:
    """Data Transfer Object returned by every ``PathPlanner.plan()`` call.

    Uniform contract for comparing coordination algorithms:

    - ``positions`` / ``moves`` — universal contract (every planner fills
      them);
    - ``order`` / ``inheritance`` / ``priorities`` — optional diagnostics
      (left empty outside the PIBT family).

    Keys are ``agent_id`` integers so the DTO stays decoupled from Agent
    objects rather than referencing them directly.

    **Frozen**, like every other value handed between the planner and its
    caller (``Coordinates2D``, ``AssignmentManifest``). One instance is
    built in a single pass and never written to afterwards, so a caller
    that holds onto it can trust it to read identically later.
    """

    positions:   dict[int, Coordinates2D] = field(default_factory=dict)   # agent_id → next Coordinates2D
    moves:       dict[int, tuple]         = field(default_factory=dict)   # agent_id → (from, to)
    order:       list[int]                = field(default_factory=list)   # agent_ids in priority order
    inheritance: list[tuple]              = field(default_factory=list)   # (pusher_id, pushed_id)
    priorities:  dict[int, float]         = field(default_factory=dict)   # agent_id → priority
