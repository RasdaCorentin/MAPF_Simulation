#!/usr/bin/env python3
"""
sim_many_pibt_plus.py — L0 benchmark: PIBT+ algorithm sweep, no pygame, no hardware.

Near-duplicate of sim_many_pibt.py (see there for the grid/seed rationale),
adjusted for PIBTPlusCoordinator: a batch algorithm that solves the whole
joint path on its first plan() call and just replays it afterwards.
`first_plan_ms` isolates that one-off solve cost — averaging it into
`mean_plan_ms` would hide it under the near-zero replay ticks that follow,
which would understate exactly the cost the cache/replay design trades off
against.

Usage:
    python sim_many_pibt_plus.py                  # full sweep, 30 seeds
    python sim_many_pibt_plus.py --seeds 5        # quick smoke-test
    python sim_many_pibt_plus.py --out my.csv     # custom output file
"""

import time
import random
import csv
import argparse
from collections import defaultdict

from core import Simulation, Agent, Grid, Position, StaticDispatcher
from algo import PIBTPlusCoordinator

# ── Defaults ──────────────────────────────────────────────────────────────────

GRIDS = [
    (4, 4),
    (5, 5),
    (8, 8),
]
ARENA_MM  = 2000
MAX_STEPS = 100
N_SEEDS   = 30
OUTPUT    = "sim_results_pibt_plus.csv"

# ── Scenario generator ────────────────────────────────────────────────────────

def make_scenario(grid_w: int, grid_h: int, n: int, seed: int):
    """Return (starts, goals) — lists of (x, y) tuples, seeded and reproducible."""
    rng = random.Random(seed)
    cells = [(x, y) for x in range(grid_w) for y in range(grid_h)]
    starts = rng.sample(cells, n)
    goals  = rng.sample(cells, n)
    return starts, goals

# ── Single instance ───────────────────────────────────────────────────────────

def _manhattan(a: Position, b: Position) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)

def run_instance(gw: int, gh: int, n: int, seed: int) -> dict:
    starts, goals_pos = make_scenario(gw, gh, n, seed)

    agents   = [Agent(i, Position(*s)) for i, s in enumerate(starts)]
    goal_map = {agents[i]: Position(*goals_pos[i]) for i in range(n)}
    optimal  = [_manhattan(agents[i].position, goal_map[agents[i]]) for i in range(n)]

    goals_by_id = {i: Position(*goals_pos[i]) for i in range(n)}
    pibt_plus   = PIBTPlusCoordinator()
    dispatcher  = StaticDispatcher(goals=goals_by_id)
    sim         = Simulation(Grid(gw, gh), coordinator=pibt_plus, dispatcher=dispatcher)
    for a in agents:
        sim.add_agent(a)

    arrival      = {i: None for i in range(n)}
    plan_ms_sum  = 0.0
    first_plan_ms = None

    for t in range(1, MAX_STEPS + 1):
        t0 = time.perf_counter()
        sim.step()
        elapsed_ms = (time.perf_counter() - t0) * 1e3
        plan_ms_sum += elapsed_ms
        if first_plan_ms is None:
            first_plan_ms = elapsed_ms

        for i, a in enumerate(agents):
            if arrival[i] is None and a.position == goal_map[a]:
                arrival[i] = t

    arrived      = sum(1 for v in arrival.values() if v is not None)
    success_rate = arrived / n
    makespan     = max((v for v in arrival.values() if v is not None), default=None)
    flowtime     = sum(v for v in arrival.values() if v is not None) if arrived else None
    deadlocks    = n - arrived
    mean_plan_ms = plan_ms_sum / MAX_STEPS

    detours = []
    for i in range(n):
        if arrival[i] is not None:
            detours.append(arrival[i] / optimal[i] if optimal[i] > 0 else 1.0)
    mean_detour = sum(detours) / len(detours) if detours else None

    return {
        "success_rate":  success_rate,
        "arrived":       arrived,
        "makespan":      makespan,
        "flowtime":      flowtime,
        "mean_detour":   mean_detour,
        "mean_plan_ms":  mean_plan_ms,
        "first_plan_ms": first_plan_ms,
        "deadlocks":     deadlocks,
    }

# ── Sweep ─────────────────────────────────────────────────────────────────────

def run_sweep(seeds: list[int], output: str) -> None:
    rows = []

    for (gw, gh) in GRIDS:
        cells   = gw * gh
        cell_mm = ARENA_MM // gw
        print(f"\n=== Grid {gw}×{gh}  ({cell_mm} mm cells,  {cells} cells) ===")

        n_max = cells
        for n in range(2, n_max + 1):
            seed_results = []
            for seed in seeds:
                try:
                    r = run_instance(gw, gh, n, seed)
                    seed_results.append(r)
                    rows.append({
                        "grid_w":       gw,
                        "grid_h":       gh,
                        "cell_mm":      cell_mm,
                        "n_agents":     n,
                        "occupancy":    round(n / cells, 4),
                        "seed":         seed,
                        "success_rate": r["success_rate"],
                        "arrived":      r["arrived"],
                        "makespan":     r["makespan"],
                        "flowtime":     r["flowtime"],
                        "mean_detour":  r["mean_detour"],
                        "mean_plan_ms": r["mean_plan_ms"],
                        "first_plan_ms": r["first_plan_ms"],
                        "deadlocks":    r["deadlocks"],
                    })
                except Exception as exc:
                    print(f"  [{gw}×{gh}] N={n} seed={seed} ERROR: {exc}")

            if seed_results:
                mean_sr  = sum(r["success_rate"] for r in seed_results) / len(seed_results)
                mean_dl  = sum(r["deadlocks"]    for r in seed_results) / len(seed_results)
                rho      = n / cells
                print(f"  N={n:2d}  ρ={rho:.2f}  success={mean_sr*100:5.1f}%  "
                      f"deadlocks_mean={mean_dl:.1f}")

    if rows:
        fieldnames = [
            "grid_w", "grid_h", "cell_mm", "n_agents", "occupancy", "seed",
            "success_rate", "arrived", "makespan", "flowtime",
            "mean_detour", "mean_plan_ms", "first_plan_ms", "deadlocks",
        ]
        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nResults written to {output}  ({len(rows)} rows)")

    _print_breaking_points(rows)

# ── Breaking-point summary ────────────────────────────────────────────────────

def _print_breaking_points(rows: list[dict]) -> None:
    print("\n=== Breaking-point summary ===")

    grouped: dict[tuple, list] = defaultdict(list)
    for row in rows:
        grouped[(row["grid_w"], row["grid_h"], row["n_agents"])].append(row)

    for (gw, gh) in GRIDS:
        cells = gw * gh
        n_star         = None
        n_50           = None
        deadlock_onset = None

        n_max = cells // 2
        for n in range(2, n_max + 1):
            key = (gw, gh, n)
            if key not in grouped:
                continue
            seed_rows = grouped[key]
            mean_sr   = sum(r["success_rate"] for r in seed_rows) / len(seed_rows)
            any_dl    = any(r["deadlocks"] > 0 for r in seed_rows)

            if mean_sr == 1.0:
                n_star = n
            if n_50 is None and mean_sr < 0.5:
                n_50 = n
            if deadlock_onset is None and any_dl:
                deadlock_onset = n

        rho_star = round(n_star / cells, 3) if n_star is not None else None
        print(
            f"  {gw}×{gh}:  N*={n_star}  ρ*={rho_star}  "
            f"N₅₀={n_50}  deadlock_onset={deadlock_onset}"
        )

# ── Entry point ───────────────────────────────────────────────────────────────

def _parse_args():
    parser = argparse.ArgumentParser(description="L0 PIBT+ benchmark sweep")
    parser.add_argument("--seeds", type=int, default=N_SEEDS,
                        help=f"number of seeds per (grid, N) cell (default: {N_SEEDS})")
    parser.add_argument("--out",   type=str, default=OUTPUT,
                        help=f"output CSV file (default: {OUTPUT})")
    return parser.parse_args()

if __name__ == "__main__":
    args  = _parse_args()
    seeds = list(range(args.seeds))
    print(f"L0 sweep (PIBT+) — {len(GRIDS)} grids, seeds 0…{args.seeds-1}, max_steps={MAX_STEPS}")
    run_sweep(seeds, args.out)
