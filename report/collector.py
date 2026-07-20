import subprocess
import time
import uuid
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from core import Position
from mrta import TaskState

from .run_record import RunRecord, SCHEMA_VERSION


class RunCollector:
    """Wraps a SimulationController and measures the run as it happens.

    A decorator, not a subclass: it forwards every attribute it does not
    define, so a frontend drives it exactly as it drives the controller and
    needs no knowledge that it is being observed.

    It measures from the **outside**, through public attributes only
    (``fleet.tasks``, ``fleet.completed_count``, ``sim.last_intent``). Nothing
    here reaches into FleetManager's internals, so the metrics can be
    reworked — and they will be — without the fleet having to care.
    """

    def __init__(self, controller, config, label: str = "") -> None:
        """Input: the controller to observe, the ScenarioConfig it was built
        from, and a free-text label for the experiment.
        Output: None.
        """
        self._controller = controller
        self._config = config
        self._label = label

        self._steps = 0
        self._wall_ms = 0.0
        self._started = time.perf_counter()

        # Task observation. FleetManager prunes a task on the same tick it
        # ends, so assignment has to be caught live, tick by tick.
        self._assigned_at: dict[int, int] = {}
        self._assigned_from: dict[int, Position] = {}
        self._states: dict[int, TaskState] = {}
        self._targets: dict[int, Position] = {}
        self._waits: list[int] = []
        self._services: list[int] = []
        self._detours: list[float] = []
        self._attempts_max = 0
        self._reassignments = 0
        self._failed_stalled = 0
        self._failed_unreachable = 0
        self._last_failed_count = 0

        # Drift observation: where an agent parked when it lost its goal, and
        # how far traffic has pushed it since.
        self._parked: dict[int, Position] = {}
        self._drift: dict[int, int] = {}
        self._displaced = 0
        self._goalless_ticks = 0
        self._busy_ticks = 0
        self._idle_max = 0

    def __getattr__(self, name):
        """Input: an attribute name.
        Output: the wrapped controller's attribute. Only reached for names
        this class does not define, so ``step`` below still wins.
        """
        return getattr(self._controller, name)

    def step(self):
        """Input: none.
        Output: the step's snapshot, after recording this tick.
        """
        t0 = time.perf_counter()
        snapshot = self._controller.step()
        self._wall_ms += (time.perf_counter() - t0) * 1e3
        self._steps += 1
        self._observe()
        return snapshot

    def run(self, steps: int) -> list:
        """Input: a number of steps. Output: one snapshot per step."""
        return [self.step() for _ in range(steps)]

    # ── Observation ──────────────────────────────────────────────────────────

    def _observe(self) -> None:
        """Input: none. Output: None. Records one tick."""
        self._observe_tasks()
        self._observe_agents()

    def _observe_tasks(self) -> None:
        """Input: none.
        Output: None. Tracks task transitions from outside the fleet.

        A task that disappears is terminal, but pruning has already removed it,
        so the transition is inferred from the state seen on the previous tick
        plus the fleet's own counters. Intake rejections never enter
        ``fleet.tasks`` at all — they show up only as a jump in failed_count
        that no live task accounts for.
        """
        fleet = self._controller.fleet
        if fleet is None:
            return

        step = self._controller.sim.current_step
        live = {}
        newly_failed = 0

        for task in fleet.tasks:
            live[task.task_id] = task.state
            self._targets.setdefault(task.task_id, task.target)
            self._attempts_max = max(self._attempts_max, task.attempts)

            previous = self._states.get(task.task_id)
            if task.state is TaskState.ASSIGNED and task.task_id not in self._assigned_at:
                self._assigned_at[task.task_id] = step
                self._assigned_from[task.task_id] = task.assignee.position
                self._waits.append(step - task.created_step)
            elif previous is TaskState.ASSIGNED and task.state is not TaskState.ASSIGNED:
                # Released by the watchdog: it may retry or give up here.
                self._reassignments += 1
                self._assigned_at.pop(task.task_id, None)
                if task.state is TaskState.FAILED:
                    self._failed_stalled += 1
                    newly_failed += 1

        for task_id, previous in self._states.items():
            if task_id in live:
                continue
            # Gone from the live list: pruned this tick.
            start = self._assigned_at.pop(task_id, None)
            origin = self._assigned_from.pop(task_id, None)
            if previous is TaskState.FAILED:
                newly_failed += 1
            elif start is not None:
                service = step - start
                self._services.append(service)
                target = self._targets.get(task_id)
                if origin is not None and target is not None:
                    optimal = self._manhattan(origin, target)
                    if optimal:
                        self._detours.append(service / optimal)

        # Whatever failed without a live task to explain it was rejected at
        # intake, before it was ever visible here.
        delta = fleet.failed_count - self._last_failed_count
        self._failed_unreachable += max(0, delta - newly_failed)
        self._last_failed_count = fleet.failed_count

        self._states = live

    def _observe_agents(self) -> None:
        """Input: none.
        Output: None. Splits agent-ticks into busy and goal-less, and measures
        how far a goal-less agent has been pushed from where it parked.
        """
        goals = self._controller.sim.last_intent.goals
        idle_now = 0

        for agent in self._controller.sim.agents:
            aid = agent.agent_id
            if aid in goals:
                self._busy_ticks += 1
                self._parked.pop(aid, None)     # working again: not parked
                continue

            idle_now += 1
            self._goalless_ticks += 1
            if aid not in self._parked:
                self._parked[aid] = agent.position
            elif agent.position != self._parked[aid]:
                self._displaced += 1
                self._drift[aid] = max(
                    self._drift.get(aid, 0),
                    self._manhattan(agent.position, self._parked[aid]),
                )
        self._idle_max = max(self._idle_max, idle_now)

    @staticmethod
    def _manhattan(a: Position, b: Position) -> int:
        """Input: two positions. Output: their Manhattan distance."""
        return abs(a.x - b.x) + abs(a.y - b.y)

    # ── Result ───────────────────────────────────────────────────────────────

    def record(self, label: Optional[str] = None) -> RunRecord:
        """Input: an optional label overriding the one given at construction.
        Output: the RunRecord for the run so far.
        """
        fleet = self._controller.fleet
        config = self._config
        agent_ticks = max(1, len(self._controller.sim.agents) * self._steps)

        done = fleet.completed_count if fleet else 0
        failed = fleet.failed_count if fleet else 0
        unfinished = len(fleet.tasks) if fleet else 0
        created = done + failed + unfinished
        drifts = list(self._drift.values())

        return RunRecord(
            run_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            schema_version=SCHEMA_VERSION,
            git_rev=_git_rev(),
            label=label if label is not None else self._label,

            width=config.width,
            height=config.height,
            agents=config.agents,
            obstacles=config.obstacles,
            algo=config.algo,
            mode=config.mode,
            task_source=config.tasks,
            seed=config.seed,
            patience=config.patience,
            max_attempts=config.max_attempts,

            steps=self._steps,
            wall_ms=round(self._wall_ms, 3),
            step_ms_mean=round(self._wall_ms / self._steps, 5) if self._steps else 0.0,

            tasks_created=created,
            tasks_done=done,
            tasks_failed=failed,
            tasks_unfinished=unfinished,
            completion_rate=round(done / created, 4) if created else None,
            failed_unreachable=self._failed_unreachable,
            failed_stalled=self._failed_stalled,
            reassignments=self._reassignments,
            attempts_max=self._attempts_max,

            wait_mean=round(mean(self._waits), 2) if self._waits else None,
            wait_max=max(self._waits) if self._waits else None,
            service_mean=round(mean(self._services), 2) if self._services else None,
            service_max=max(self._services) if self._services else None,
            detour_mean=round(mean(self._detours), 3) if self._detours else None,
            detour_max=round(max(self._detours), 3) if self._detours else None,

            drift_agents=len(drifts),
            drift_mean=round(mean(drifts), 2) if drifts else 0.0,
            drift_max=max(drifts) if drifts else 0,
            displaced_events=self._displaced,
            goalless_frac=round(self._goalless_ticks / agent_ticks, 4),

            busy_frac=round(self._busy_ticks / agent_ticks, 4),
            idle_max=self._idle_max,
        )


def _git_rev() -> str:
    """Input: none.
    Output: the short git revision, or "unknown" outside a repository.

    Stored on every row so a result stays attributable to the code that
    produced it — without it, a dataset spanning a refactor is unreadable.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
