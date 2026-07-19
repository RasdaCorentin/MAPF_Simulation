#!/usr/bin/env python3
"""
sim_many_mrta.py — MRTA post-run report: task lifecycle, not MAPF metrics.

Sweeps grid x fleet size x seeds under a random task load and writes one row
per instance to mrta_results.csv.

Why these columns and not the L0 ones
─────────────────────────────────────
sim_many_pibt.py answers "does PIBT route agents to fixed goals". Its
success_rate latches on the FIRST time an agent touches its goal and is never
invalidated, so a fleet that converges and then scatters still scores 100%.
That metric structurally cannot see the two failure modes MRTA actually has:

  1. a completed task releases its goal, so the agent becomes a goal-less
     obstacle that traffic ratchets away from where it parked;
  2. a stalled pairing burns patience and gets reassigned, silently, until
     the task is FAILED.

Every distribution below is reported as **mean AND max**, on purpose: the
whole bug class is "nineteen agents are fine and one is not", and a mean is
exactly the statistic that hides it.

Usage:
    python sim_many_mrta.py                    # full sweep
    python sim_many_mrta.py --seeds 2          # quick smoke-test
    python sim_many_mrta.py --out my.csv
    python sim_many_mrta.py --per-task tasks.csv    # drill-down, one row/task
"""

import time
import csv
import argparse
from statistics import mean

from core import Position
from client.control import ScenarioConfig, build
from mrta import FleetManager, TaskSource, TaskState


class RecordingSource(TaskSource):
    """Pass-through source that remembers what the last poll produced.

    FleetManager rejects an unreachable task inside _intake without ever
    putting it in self.tasks, so it is unobservable from the outside. Keeping
    the polled objects lets the report tell an accepted task from a refused
    one by identity, instead of inferring it from counter arithmetic.
    """

    def __init__(self, inner: TaskSource) -> None:
        """Input: the source to wrap. Output: None."""
        self.inner = inner
        self.last: list = []

    def poll(self, current_step: int) -> list:
        """Input: the current step. Output: the wrapped source's tasks."""
        self.last = self.inner.poll(current_step)
        return self.last

# ── Sweep definition ──────────────────────────────────────────────────────────

GRIDS      = [(8, 8), (12, 12), (15, 15)]
FLEETS     = [4, 8, 12, 20]
N_SEEDS    = 5
STEPS      = 150
OUTPUT     = "mrta_results.csv"
TASK_EVERY = 4
TASK_COUNT = 2


# ── Instrumentation ───────────────────────────────────────────────────────────

class InstrumentedFleet(FleetManager):
    """FleetManager that archives terminal tasks instead of only counting them.

    Subclassed rather than changing production code: _prune() drops terminal
    tasks precisely so the live list stays bounded, and a long-running fleet
    must not accumulate history. A benchmark run is bounded, so it can.

    Archived rows copy VALUES out of the Task — a Task keeps being mutated and
    then pruned, so keeping the object would let the archive rewrite itself.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.archive: list[dict] = []          # terminal tasks, by value
        self.reassignments = 0                 # watchdog releases
        self.failed_unreachable = 0            # rejected at intake
        self.failed_stalled = 0                # gave up after max_attempts
        self.dispatch_ms = 0.0
        self._step = 0

    def dispatch(self, agents, grid, step):
        self._step = step
        t0 = time.perf_counter()
        intent = super().dispatch(agents, grid, step)
        self.dispatch_ms += (time.perf_counter() - t0) * 1e3
        return intent

    def _watchdog(self, step):
        assigned_before = {
            t.task_id for t in self.tasks if t.state is TaskState.ASSIGNED
        }
        super()._watchdog(step)
        for task in self.tasks:
            if task.task_id in assigned_before and task.state is not TaskState.ASSIGNED:
                self.reassignments += 1
                if task.state is TaskState.FAILED:
                    self.failed_stalled += 1

    def _intake(self, step, grid):
        before = {id(t) for t in self.tasks}
        super()._intake(step, grid)          # polls through the recorder
        self.failed_unreachable += sum(
            1 for t in self.source.last if t.state is TaskState.FAILED
        )
        # Rejected tasks never enter self.tasks, so _prune() will never see
        # them. Archive them here, or the per-task report silently loses exactly
        # the rows a reader wants: which target was refused, and when.
        # FleetManager stamps the id before rejecting, so the object is complete.
        live = {id(t) for t in self.tasks}
        for task in self.source.last:
            if id(task) not in live and id(task) not in before:
                self.archive.append({
                    "task_id":      task.task_id,
                    "target":       task.target,
                    "state":        "failed_unreachable",
                    "created_step": task.created_step,
                    "end_step":     step,
                    "attempts":     task.attempts,
                })

    def _prune(self):
        for task in self.tasks:
            if task.state in (TaskState.DONE, TaskState.FAILED):
                self.archive.append({
                    "task_id":      task.task_id,
                    "target":       task.target,
                    "state":        task.state.value,
                    "created_step": task.created_step,
                    "end_step":     self._step,
                    "attempts":     task.attempts,
                })
        super()._prune()


def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


# ── Single instance ───────────────────────────────────────────────────────────

def run_instance(gw: int, gh: int, n: int, seed: int, steps: int,
                 patience: int, max_attempts: int,
                 obstacles: int = 0) -> tuple[dict, list[dict]]:
    """Input: grid size, fleet size, seed, horizon, watchdog tuning and how
    many blocking entities to scatter.
    Output: (instance row, per-task rows).
    """
    config = ScenarioConfig(
        width=gw, height=gh, agents=n, obstacles=obstacles, seed=seed,
        tasks="random", task_every=TASK_EVERY, task_count=TASK_COUNT,
        patience=patience, max_attempts=max_attempts,
    )
    controller = build(config)

    # Swap in the instrumented fleet, keeping the factory's wiring.
    fleet = InstrumentedFleet(
        source=RecordingSource(controller.fleet.source),
        allocator=controller.fleet.allocator,
        patience=patience,
        max_attempts=max_attempts,
    )
    controller.fleet = fleet
    controller.sim.dispatcher = fleet

    # Per-task observation: FleetManager prunes on the same tick a task ends,
    # so assignment has to be caught live, tick by tick.
    assigned_at: dict[int, int] = {}
    assigned_from: dict[int, Position] = {}
    assignee_of: dict[int, int] = {}

    # Drift observation (failure mode 1): where an agent parked when it went
    # goal-less, and how far traffic has pushed it since.
    parked: dict[int, Position] = {}
    drift: dict[int, int] = {}
    displaced_events = 0
    goalless_ticks = 0
    busy_ticks = 0
    idle_max = 0
    step_ms = 0.0

    for _ in range(steps):
        t0 = time.perf_counter()
        controller.step()
        step_ms += (time.perf_counter() - t0) * 1e3

        for task in fleet.tasks:
            if task.state is TaskState.ASSIGNED and task.task_id not in assigned_at:
                assigned_at[task.task_id] = controller.sim.current_step
                assigned_from[task.task_id] = task.assignee.position
                assignee_of[task.task_id] = task.assignee.agent_id

        goals = controller.sim.last_intent.goals
        idle_now = 0
        for agent in controller.sim.agents:
            aid = agent.agent_id
            if aid in goals:
                busy_ticks += 1
                parked.pop(aid, None)          # working again: not parked
                continue

            idle_now += 1
            goalless_ticks += 1
            if aid not in parked:
                parked[aid] = agent.position   # just went idle here
            elif agent.position != parked[aid]:
                displaced_events += 1
                drift[aid] = max(drift.get(aid, 0), _manhattan(agent.position, parked[aid]))
        idle_max = max(idle_max, idle_now)

    # ── Per-task rows ────────────────────────────────────────────────────────
    task_rows = []
    for rec in fleet.archive:
        tid = rec["task_id"]
        start = assigned_at.get(tid)
        origin = assigned_from.get(tid)
        wait = (start - rec["created_step"]) if start is not None else None
        service = (rec["end_step"] - start) if start is not None else None
        optimal = _manhattan(origin, rec["target"]) if origin is not None else None
        detour = (service / optimal) if (service and optimal) else None
        task_rows.append({
            "grid_w": gw, "grid_h": gh, "n_agents": n, "seed": seed,
            "task_id": tid, "agent_id": assignee_of.get(tid),
            "target_x": rec["target"].x, "target_y": rec["target"].y,
            "state": rec["state"], "attempts": rec["attempts"],
            "created_step": rec["created_step"], "end_step": rec["end_step"],
            "wait_steps": wait, "service_steps": service,
            "optimal_steps": optimal,
            "detour": round(detour, 3) if detour else None,
        })

    done = [r for r in task_rows if r["state"] == "done"]
    waits    = [r["wait_steps"]    for r in done if r["wait_steps"] is not None]
    services = [r["service_steps"] for r in done if r["service_steps"] is not None]
    detours  = [r["detour"]        for r in done if r["detour"] is not None]
    drifts   = list(drift.values())

    created = len(fleet.archive) + len(fleet.tasks) + fleet.failed_unreachable
    agent_ticks = n * steps

    row = {
        # ── scenario ──
        "grid_w": gw, "grid_h": gh, "n_agents": n,
        "occupancy": round(n / (gw * gh), 4),
        "obstacles": obstacles,
        "seed": seed, "patience": patience, "max_attempts": max_attempts,
        "steps": steps,
        # ── throughput: is work getting done at all ──
        "tasks_created": created,
        "tasks_done": fleet.completed_count,
        "tasks_failed": fleet.failed_count,
        "tasks_unfinished": len(fleet.tasks),
        "completion_rate": round(fleet.completed_count / created, 4) if created else None,
        # ── latency: where the time goes ──
        "wait_mean":    round(mean(waits), 2) if waits else None,
        "wait_max":     max(waits) if waits else None,
        "service_mean": round(mean(services), 2) if services else None,
        "service_max":  max(services) if services else None,
        "detour_mean":  round(mean(detours), 3) if detours else None,
        "detour_max":   max(detours) if detours else None,
        # ── robustness: the watchdog's view ──
        "reassignments":      fleet.reassignments,
        "failed_unreachable": fleet.failed_unreachable,
        "failed_stalled":     fleet.failed_stalled,
        "attempts_max":       max((r["attempts"] for r in task_rows), default=0),
        # ── formation drift: goal released on completion ──
        "drift_agents": len(drifts),
        "drift_mean":   round(mean(drifts), 2) if drifts else 0,
        "drift_max":    max(drifts) if drifts else 0,
        "displaced_events": displaced_events,
        "goalless_frac": round(goalless_ticks / agent_ticks, 4),
        # ── fleet utilisation ──
        "busy_frac": round(busy_ticks / agent_ticks, 4),
        "idle_max":  idle_max,
        # ── cost, split so the allocator and the planner are separable ──
        "dispatch_ms_mean": round(fleet.dispatch_ms / steps, 5),
        "plan_ms_mean":     round((step_ms - fleet.dispatch_ms) / steps, 5),
    }
    return row, task_rows


# ── Sweep ─────────────────────────────────────────────────────────────────────

def run_sweep(seeds: list[int], steps: int, output: str,
              per_task: str | None, patience: int, max_attempts: int,
              obstacles: int) -> None:
    """Input: seeds, horizon, output paths and watchdog tuning.
    Output: None. Writes the CSV(s) and prints a summary.
    """
    rows, task_rows = [], []

    for (gw, gh) in GRIDS:
        print(f"\n=== Grid {gw}x{gh} ({gw * gh} cells) ===")
        for n in FLEETS:
            if n > gw * gh:
                continue
            batch = []
            for seed in seeds:
                try:
                    row, tasks = run_instance(gw, gh, n, seed, steps,
                                              patience, max_attempts, obstacles)
                    rows.append(row)
                    task_rows.extend(tasks)
                    batch.append(row)
                except Exception as exc:
                    print(f"  [{gw}x{gh}] N={n} seed={seed} ERROR: {exc}")

            if batch:
                print(
                    f"  N={n:3}  done={mean(r['tasks_done'] for r in batch):5.1f}"
                    f"  failed={mean(r['tasks_failed'] for r in batch):4.1f}"
                    f"  reassign={mean(r['reassignments'] for r in batch):4.1f}"
                    f"  drift_max={max(r['drift_max'] for r in batch):3}"
                    f"  busy={mean(r['busy_frac'] for r in batch):.2f}"
                )

    if rows:
        with open(output, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nInstance report -> {output}  ({len(rows)} rows)")

    if per_task and task_rows:
        with open(per_task, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(task_rows[0]))
            writer.writeheader()
            writer.writerows(task_rows)
        print(f"Per-task report -> {per_task}  ({len(task_rows)} rows)")

    _print_summary(rows)


def _print_summary(rows: list[dict]) -> None:
    """Input: the instance rows.
    Output: None. Prints what a debugging read should look at first.
    """
    if not rows:
        return
    print("\n=== What to look at first ===")

    worst_drift = max(rows, key=lambda r: r["drift_max"])
    print(f"  worst formation drift : {worst_drift['drift_max']} cells "
          f"({worst_drift['grid_w']}x{worst_drift['grid_h']}, N={worst_drift['n_agents']}, "
          f"seed={worst_drift['seed']})  — agents pushed off a completed target")

    stalled = [r for r in rows if r["failed_stalled"]]
    print(f"  instances with a stalled task : {len(stalled)}/{len(rows)}")

    worst_detour = max((r for r in rows if r["detour_max"]),
                       key=lambda r: r["detour_max"], default=None)
    if worst_detour:
        print(f"  worst detour          : x{worst_detour['detour_max']:.1f} "
              f"({worst_detour['grid_w']}x{worst_detour['grid_h']}, "
              f"N={worst_detour['n_agents']}, seed={worst_detour['seed']})")

    print(f"  mean goal-less time   : {mean(r['goalless_frac'] for r in rows):.1%} "
          f"of agent-ticks  — the window in which an agent can be pushed for free")


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    """Input: none (reads sys.argv). Output: parsed arguments."""
    parser = argparse.ArgumentParser(description="MRTA post-run report")
    parser.add_argument("--seeds", type=int, default=N_SEEDS)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--out", type=str, default=OUTPUT)
    parser.add_argument("--per-task", type=str, default=None,
                        help="also write one row per task to this file")
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--obstacles", type=int, default=0,
                        help="blocking entities per instance; exercises the "
                             "unreachable-target and stalled-task paths")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"MRTA sweep — {len(GRIDS)} grids, fleets {FLEETS}, "
          f"seeds 0..{args.seeds - 1}, {args.steps} steps")
    run_sweep(list(range(args.seeds)), args.steps, args.out,
              args.per_task, args.patience, args.max_attempts, args.obstacles)
