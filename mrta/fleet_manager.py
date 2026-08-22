from typing import Optional

from core import (
    Agent, SpatialIndex, Coordinates2D, AssignmentManifest, MissionOrchestrator,
    manhattan_distance,
)

from .task import Mission, MissionState
from .task_source import MissionSource
from .allocator import AssignmentStrategy


class TaskDrivenOrchestrator(MissionOrchestrator):
    """Control loop bridging mission sources and allocation, as a MissionOrchestrator.

    Pure with respect to the engine: ``assign_missions()`` reads state,
    updates mission assignments, and returns an ``AssignmentManifest``
    describing the complete goals/priorities of the active missions — it
    never touches the planner.

    One cycle, in order:
        complete -> watchdog -> prune -> intake -> allocate -> manifest

    The watchdog lives here because TaskDrivenOrchestrator is the only
    component that sees a mission's life *across* ticks. Putting it in
    the planner would re-couple navigation with allocation semantics —
    exactly what AssignmentManifest separated.
    """

    def __init__(
        self,
        source: MissionSource,
        allocator: AssignmentStrategy,
        patience: int = 12,
        max_attempts: int = 3,
    ) -> None:
        """Input: the mission source, the allocation strategy, how many
        steps an assignee may go without getting closer to its target
        before being released, and how many assignees a mission may burn
        through before it is failed.
        Output: None.
        """
        self.source = source
        self.allocator = allocator
        self.patience = patience
        self.max_attempts = max_attempts
        self.tasks: list[Mission] = []
        self.completed_count = 0
        self.failed_count = 0
        # Mission identity is stamped here, not by the sources: Mission
        # hashes on task_id and is used as a dict key by AssignmentStrategy,
        # so two sources numbering from zero would silently collapse each
        # other's missions. The registry owns identity within it.
        self._next_task_id = 0

    def assign_missions(
        self, agents: list[Agent], grid: SpatialIndex, step: int
    ) -> AssignmentManifest:
        """Input: all simulated agents, the grid, and the current step.
        Output: the AssignmentManifest (goals/priorities) for the active
        missions after one full cycle.
        """
        self._finalize_arrived_missions(agents)
        self._release_stalled_assignees(step)
        self._archive_terminal_missions()
        self._intake_new_missions(step, grid)
        self._run_allocation_pass(agents, grid)
        return self._compile_assignment_manifest()

    def set_mission_priority(self, task_id: int, priority: float) -> None:
        """Input: a mission id and its new priority.
        Output: None. Updates the mission; the new value reaches the
        planner through the next manifest.
        """
        for task in self.tasks:
            if task.task_id == task_id:
                task.priority = priority
                return

    # ── Cycle stages ─────────────────────────────────────────────────────────

    def _finalize_arrived_missions(self, agents: list[Agent]) -> None:
        """Input: all simulated agents.
        Output: None. Marks assigned missions whose assignee stands on the
        target as DONE.

        Sampling ``agent.position`` is exact here, not an approximation:
        assign_missions runs every tick and an agent advances at most one
        cell per tick, so no cell can be stepped over between two samples.
        """
        for task in self.tasks:
            if task.state is MissionState.ASSIGNED and task.assignee is not None:
                if task.assignee.position == task.target:
                    task.state = MissionState.DONE

    def _release_stalled_assignees(self, step: int) -> None:
        """Input: the current simulation step.
        Output: None. Releases assignees that have stopped making
        progress, and fails missions that burned through too many of them.

        We do not try to *prove* a target reachable — reachability is not
        static in a world with deferred spawns, and proving it would
        duplicate the planner. We observe the absence of progress
        instead: if the Manhattan distance to the target has not improved
        for ``patience`` steps, this pairing is going nowhere.
        """
        for task in self.tasks:
            if task.state is not MissionState.ASSIGNED or task.assignee is None:
                continue

            distance = manhattan_distance(task.assignee.position, task.target)
            if task.best_distance is None or distance < task.best_distance:
                task.best_distance = distance
                task.last_improvement_step = step
                continue

            if step - task.last_improvement_step < self.patience:
                continue

            # Stalled: free the agent so it is not consumed forever.
            task.assignee = None
            task.attempts += 1
            task.best_distance = None
            task.last_improvement_step = step
            if task.attempts >= self.max_attempts:
                task.state = MissionState.FAILED
            else:
                task.state = MissionState.PENDING

    def _archive_terminal_missions(self) -> None:
        """Input: none.
        Output: None. Drops terminal missions, counting them on the way
        out so that finished and abandoned work stays observable after
        the mission object is gone.
        """
        kept = []
        for task in self.tasks:
            if task.state is MissionState.DONE:
                self.completed_count += 1
            elif task.state is MissionState.FAILED:
                self.failed_count += 1
            else:
                kept.append(task)
        self.tasks = kept

    def _intake_new_missions(self, step: int, grid: SpatialIndex) -> None:
        """Input: the current simulation step and the grid.
        Output: None. Fetches new missions from the source and registers
        them, failing immediately those whose target is off the grid or
        sits under a blocking entity — a mission no agent could ever
        complete should not be allowed to consume one.
        """
        for task in self.source.fetch_new_missions(step):
            task.task_id = self._next_task_id
            self._next_task_id += 1
            if not grid.is_within_bounds(task.target) or self._target_is_unreachable(task.target, grid):
                task.state = MissionState.FAILED
                self.failed_count += 1
                continue
            task.last_improvement_step = step
            self.tasks.append(task)

    def _run_allocation_pass(self, agents: list[Agent], grid: SpatialIndex) -> None:
        """Input: all simulated agents and the grid.
        Output: None. Matches pending missions to free agents through the
        allocation strategy and records the assignments.

        Missions are grouped by eligibility class and the strategy is
        called once per class, unrestricted missions last, with matched
        agents removed from the pool between calls. Eligibility is thus
        enforced without the AssignmentStrategy interface knowing about
        it: a restriction on *who may be asked* belongs to the request,
        while the strategy only decides *how to match*.
        """
        pending = [t for t in self.tasks if t.state is MissionState.PENDING]
        if not pending:
            return

        assigned_agent_ids = {
            t.assignee.agent_id for t in self.tasks
            if t.state is MissionState.ASSIGNED and t.assignee is not None
        }
        free = [a for a in agents if a.agent_id not in assigned_agent_ids]
        if not free:
            return

        for eligible, group in self._filter_eligible_units(pending):
            if not free:
                return
            pool = free if eligible is None else [a for a in free if a.agent_id in eligible]
            if not pool:
                continue

            matches = self.allocator.match_missions_to_units(group, pool, grid)
            taken = set()
            for task, agent in matches.items():
                task.state = MissionState.ASSIGNED
                task.assignee = agent
                task.best_distance = None
                taken.add(agent.agent_id)
            free = [a for a in free if a.agent_id not in taken]

    def _compile_assignment_manifest(self) -> AssignmentManifest:
        """Input: none.
        Output: an AssignmentManifest with, for every ASSIGNED mission,
        its assignee's goal and allocation priority.
        """
        goals: dict[int, Coordinates2D] = {}
        priorities: dict[int, float] = {}
        for task in self.tasks:
            if task.state is MissionState.ASSIGNED and task.assignee is not None:
                aid = task.assignee.agent_id
                goals[aid] = task.target
                priorities[aid] = task.priority
        return AssignmentManifest(goals=goals, priorities=priorities)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _filter_eligible_units(
        pending: list[Mission],
    ) -> list[tuple[Optional[frozenset[int]], list[Mission]]]:
        """Input: the pending missions.
        Output: (eligibility, missions) groups, restricted classes first
        so that a mission naming specific agents is served before an
        unrestricted one can take them.
        """
        groups: dict[Optional[frozenset[int]], list[Mission]] = {}
        for task in pending:
            groups.setdefault(task.eligible, []).append(task)
        ordered = [(k, v) for k, v in groups.items() if k is not None]
        if None in groups:
            ordered.append((None, groups[None]))
        return ordered

    @staticmethod
    def _target_is_unreachable(position: Coordinates2D, grid: SpatialIndex) -> bool:
        """Input: a position and the grid.
        Output: True if an active blocking entity (not an agent) sits there.
        """
        return any(
            e.blocks_movement and e.is_active
            for e in grid.entities_at(position)
            if not isinstance(e, Agent)
        )
