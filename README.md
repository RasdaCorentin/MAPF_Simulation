# MAPF Simulation

A small **Multi-Agent Path Finding (MAPF)** simulator: a pure engine (`core/`) with a
pluggable `PathPlanner`/`MissionOrchestrator` interface, and a concrete implementation of
both (`pibt/`, Priority Inheritance with Backtracking) that runs end to end today.

![Class diagram](diagrammes/Class_Diagram/simulation_class_diagram_commente.png)

## Inspiration & attribution

`pibt/`'s planner is an **independent reimplementation** inspired by the work of
**Okumura et al.**:

> Keisuke Okumura, Manao Machida, Xavier Défago, Yasumasa Tamura.
> *"Priority Inheritance with Backtracking for Iterative Multi-Agent Path Finding."*
> Artificial Intelligence, 2022 (originally IJCAI 2019).
> [arXiv:1901.11282](https://arxiv.org/abs/1901.11282)

This repository is a learning/demo project and is **not** affiliated with the original
authors.

## Features

- **Pure simulation core** (`core/`) with zero rendering dependency: grid, agents,
  deferred spawns, impassable obstacles, and the `WorldEngine` tick.
- **Pluggable `PathPlanner`** — drop in any MAPF algorithm; every `plan()` returns a
  uniform `StepOutcome`. `pibt/PIBTPlanner` is the concrete one provided.
- **Pluggable `MissionOrchestrator`** — decides what each agent's goal is, every tick.
  `pibt/` provides two: `OneShotGoalDispatcher` (one fixed goal per agent for the whole
  run) and `LifelongGoalOrchestrator` (one externally-settable target per agent, via
  `set_target(agent_id, position)` — built for an event- or click-driven caller).
- **CSV run logging**, opt-in (`export/`): a per-tick trace, a per-run summary that
  appends across runs, and a `CompositeExporter` to fan out to both at once.

## Requirements

- Python 3.10+
- No runtime dependencies (`pyproject.toml` declares none)

## Installation

**As a dependency in another project** — no local checkout needed:

```bash
pip install "mapf-simulation @ git+ssh://git@github.com/RasdaCorentin/MAPF_Simulation.git@develop"
```

(use `git+https://github.com/RasdaCorentin/MAPF_Simulation.git@develop` instead if the
caller has no SSH key configured for this remote). This installs `core` and `pibt` as
top-level importable packages — see [`AGENT.md`](AGENT.md#installing-this-repo-into-another-project)
for what each one exposes.

**For local development** — clone, then install this checkout itself:

```bash
git clone git@github.com:RasdaCorentin/MAPF_Simulation.git
cd MAPF_Simulation
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Running it

```bash
python -m pibt.demo_one_shot     # 3 agents cross the grid to fixed goals, runs to convergence
python -m pibt.demo_lifelong     # 3 agents keep getting re-targeted; runs for a fixed step count
python demo_trace_log.py         # same idea, plus a per-tick CSV trace under log/trace/
python demo_aggregate_log.py     # 3 runs, each appending one summary row to log/aggregate.csv
```

`main.py` and every `sim_many_*.py` sweep are **not** currently runnable — see
[`TODO.md`](TODO.md) for exactly why and what bringing them back needs.

## Project structure

```
core/       pure simulation engine — entities/ (Coordinates2D, WorldEntity, Orientation,
            Agent, Objective), environment/ (Grid2D), engine/ (WorldEngine, PathPlanner,
            MissionOrchestrator, StepOutcome, AssignmentManifest)
pibt/       concrete PathPlanner (PIBTPlanner) + two concrete MissionOrchestrators
            (OneShotGoalDispatcher, LifelongGoalOrchestrator) — depends only on core
export/     concrete Exporters (TraceCsvExporter, AggregateCsvExporter, CompositeExporter)
            — depends only on core
diagrammes/ PlantUML class diagram sources + generated PNGs
```

`core/` has no outgoing dependencies of its own; `pibt/` and `export/` each depend only on
`core`, not on each other. See [`AGENT.md`](AGENT.md) for the full architecture reference,
the dependency rules, and a per-package guide (`core/AGENT.md`, `pibt/AGENT.md`,
`export/AGENT.md`).

## Adding your own algorithm

Subclass `PathPlanner` and implement `plan()`, returning a `StepOutcome`. Goals and
priorities arrive through the tick's `AssignmentManifest`, as a list of `Objective`s each
already bound to the one `Agent` allowed to complete it:

```python
from core import PathPlanner, StepOutcome

class MyAlgo(PathPlanner):
    def plan(self, agents, grid, intent) -> StepOutcome:
        goal_by_agent = {o.assignee.agent_id: o.position for o in intent.goals if o.assignee}
        positions = {a.agent_id: goal_by_agent.get(a.agent_id, a.position) for a in agents}
        moves = {a.agent_id: (a.position, positions[a.agent_id]) for a in agents}
        return StepOutcome(positions=positions, moves=moves)
```

Wire it in with `WorldEngine(grid, planner=MyAlgo())`. `pibt/pibt_planner.py` is a working
reference implementation to copy the shape of; `pibt/one_shot_dispatcher.py` and
`pibt/lifelong_orchestrator.py` are the same for `MissionOrchestrator`. Without one
attached, `intent` is an empty `AssignmentManifest()` every tick, so a planner sees no
goals and every agent stays put.

## Documentation map

| File            | Audience     | Purpose                                       |
|:----------------|:-------------|:-----------------------------------------------|
| `README.md`     | everyone     | this file — overview, install, run             |
| `AGENT.md`      | agents/devs  | exhaustive architecture reference, per-package guides |
| `CONVENTION.md` | contributors | git, branch, commit and issue conventions      |
| `TODO.md`       | everyone     | what's broken right now, and why               |

## License

[MIT](LICENSE) © 2026 Arcko5
