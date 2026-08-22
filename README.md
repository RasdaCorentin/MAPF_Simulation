# MAPF Simulation — PIBT

A small **Multi-Agent Path Finding (MAPF)** simulator with a pluggable coordinator
interface. The flagship coordinator implements **PIBT** (Priority Inheritance with
Backtracking).

> **Currently a library, not a runnable demo.** `main.py` and `sim_many_mrta.py` are
> broken — see [`TODO.md`](TODO.md) — pending a deliberate redesign of how a caller is meant
> to drive a scenario. `core/`, `algo/`, `mrta/` and the three static-mode `sim_many_*.py`
> sweeps below are unaffected and work today.

![Class diagram](diagrammes/Class_Diagram/simulation_class_diagram_commente.png)

## Inspiration & attribution

The PIBT coordinator in
[`algo/coordination/pibt_coordinator.py`](algo/coordination/pibt_coordinator.py) is an
**independent reimplementation** inspired by the work of **Okumura et al.**:

> Keisuke Okumura, Manao Machida, Xavier Défago, Yasumasa Tamura.
> *"Priority Inheritance with Backtracking for Iterative Multi-Agent Path Finding."*
> Artificial Intelligence, 2022 (originally IJCAI 2019).
> [arXiv:1901.11282](https://arxiv.org/abs/1901.11282)

This repository is a learning/demo project and is **not** affiliated with the
original authors.

## Features

- **Pure simulation core** (`core/`) with zero rendering dependency.
- **Pluggable `Coordinator` interface** — drop in any MAPF algorithm; every `plan()`
  returns a uniform `PlanResult` DTO.
- Two coordinators provided: **PIBT** and a minimal **random walk**.
- **Task allocation** (`mrta/`): tasks with a full lifecycle (including failure and a
  progress watchdog), several task sources, an allocator interface, and a fleet
  manager that dispatches goals to the shared coordinator.
- Deferred spawns and impassable obstacles.

## Requirements

- Python 3.10+ (developed on 3.14)
- No runtime dependencies (`requirements.txt` is currently empty)

## Installation

```bash
# (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## Running it

`main.py` and `sim_many_mrta.py` are currently broken (see the note above and
[`TODO.md`](TODO.md)). What works today, run from the repository root:

```bash
python sim_many_pibt.py --seeds 2               # headless PIBT benchmark sweep
python sim_many_lacam.py --seeds 2              # same, LaCAM
python sim_many_pibt_plus.py --seeds 2          # same, PIBT+
```

## Project structure

```
core/       pure simulation engine — entities/ (Position, WorldEntity, Agent),
            environment/ (Grid), engine/ (Simulation, Coordinator, PlanResult)
algo/       MAPF algorithms — coordination/ (PIBT, random walk), allocation/
mrta/       Multi-Robot Task Allocation (Task, TaskSource, Allocator, FleetManager)
diagrammes/ PlantUML class diagram sources + generated PNGs
main.py     CLI entry point — BROKEN, see TODO.md
```

Dependencies are strictly one-directional:

```
mrta → core
algo → core, mrta
```

`core/` never imports the others. See [`GUIDE.md`](GUIDE.md) for a human tour of the project
and [`AGENT.md`](AGENT.md) for the full architecture reference.

## Adding your own algorithm

Subclass `Coordinator` and implement `plan()`, returning a `PlanResult`. Goals and
priorities arrive through the tick's `DispatchIntent`:

```python
from core import Coordinator, PlanResult

class MyAlgo(Coordinator):
    def plan(self, agents, grid, intent) -> PlanResult:
        positions = {a.agent_id: intent.goals.get(a.agent_id, a.position) for a in agents}
        moves = {a.agent_id: (a.position, positions[a.agent_id]) for a in agents}
        return PlanResult(positions=positions, moves=moves)
```

Wire it in with a dispatcher that supplies the goals — a `StaticDispatcher` for fixed
targets, or a `FleetManager` (mrta) for task allocation:
`Simulation(grid, coordinator=MyAlgo(), dispatcher=StaticDispatcher(goals={...}))`. See
[`algo/coordination/random_walk.py`](algo/coordination/random_walk.py) for a minimal
working example.

## License

[MIT](LICENSE) © 2026 Arcko5
