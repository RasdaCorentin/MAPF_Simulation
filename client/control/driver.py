from abc import ABC, abstractmethod
from typing import Iterable, Optional

from core import Position, Simulation
from mrta import FleetManager, QueueTaskSource, Task

from client.view import StepSnapshot


class SimulationDriver(ABC):
    """What a frontend is allowed to drive.

    ``SimulationController`` is the ordinary implementation; ``RunCollector``
    (in ``report``) is a decorator that wraps one and measures it. Both are
    handed to frontends interchangeably, so the thing a frontend depends on
    is this interface, not the controller class.

    **Why an interface rather than duck typing.** A decorator is only a
    decorator if it presents the same face as what it wraps — that is what
    makes it substitutable. Without a declared contract the substitution
    rested on ``__getattr__`` forwarding, which no one checks: a collector
    that forgot a method would fail at the first click in the window rather
    than at import. Declaring the contract also lets the class diagram say
    what is actually true, in both the measured and unmeasured cases.

    The attribute half of the contract (``sim``, ``fleet``, ``queue``) is
    part of it because ``PygameFrontend`` genuinely reads ``sim.grid`` and
    ``sim.agents`` to hit-test clicks. That is a wider seam than the prose in
    AGENT.md claims ("frontends never touch Simulation"); this interface
    records the seam that exists rather than the one we would prefer.
    Narrowing it — routing hit-testing through StepSnapshot — is a separate
    change, and this ABC is where it would be enforced.
    """

    # ── The wrapped scenario ─────────────────────────────────────────────────

    @property
    @abstractmethod
    def sim(self) -> Simulation:
        """The simulation being driven."""
        ...

    @property
    @abstractmethod
    def fleet(self) -> Optional[FleetManager]:
        """The fleet, in MRTA mode; None in static mode."""
        ...

    @property
    @abstractmethod
    def queue(self) -> Optional[QueueTaskSource]:
        """The interactive task queue, in MRTA mode; None in static mode."""
        ...

    # ── Driving ──────────────────────────────────────────────────────────────

    @abstractmethod
    def step(self) -> StepSnapshot:
        """Input: none. Output: the snapshot of the step just executed."""
        ...

    @abstractmethod
    def run(self, steps: int) -> list[StepSnapshot]:
        """Input: a number of steps. Output: one snapshot per step."""
        ...

    @abstractmethod
    def snapshot(self) -> StepSnapshot:
        """Input: none. Output: a snapshot of the current state."""
        ...

    # ── Tasking ──────────────────────────────────────────────────────────────

    @abstractmethod
    def send_batch_to(
        self,
        target: Position,
        agent_ids: Optional[Iterable[int]] = None,
        priority: float = 5.0,
    ) -> list[Task]:
        """Input: a destination, the agents allowed to serve it, a priority.
        Output: the tasks minted and queued.
        """
        ...
