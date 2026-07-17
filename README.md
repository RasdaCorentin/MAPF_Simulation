# MAPF Simulation — PIBT

A small **Multi-Agent Path Finding (MAPF)** simulator with a pluggable coordinator
interface and an interactive `pygame` viewer. The flagship coordinator implements
**PIBT** (Priority Inheritance with Backtracking).

![Class diagram](diagrammes/simulation_class_diagram_commente.png)

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
- **Task allocation** (`mrta/`): tasks, a task source, an allocator interface and a
  fleet manager that dispatches goals to the shared coordinator.
- **Interactive step-by-step viewer**: priority order, per-agent moves, and
  priority-inheritance chains shown live, with free back/forward navigation.
- Deferred spawns and impassable obstacles.

## Requirements

- Python 3.10+ (developed on 3.14)
- [pygame](https://www.pygame.org/) (see `requirements.txt`)

## Installation

```bash
# (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Running the demos

Run from the repository root:

```bash
python demo_pibt.py       # interactive PIBT demo (5×5 grid, navigable)
python demo_pibt.py -d    # terminal debug mode — prints each step, no pygame window
python main.py            # random-walk demo (10×10 grid)
```

### Interactive controls

| Key            | Action            |
| -------------- | ----------------- |
| `Space`        | play / pause      |
| `→`            | step forward      |
| `←`            | step back         |
| `Q` / `Esc`    | quit              |

## Project structure

```
core/      pure simulation engine — entities/ (Position, WorldEntity, Agent),
           environment/ (Grid), engine/ (Simulation, Coordinator, PlanResult)
algo/      MAPF algorithms — coordination/ (PIBT, random walk), allocation/
mrta/      Multi-Robot Task Allocation (Task, TaskSource, Allocator, FleetManager)
client/    pygame rendering
diagrammes/ PlantUML class diagram sources + generated PNGs
demo_pibt.py interactive PIBT entry point
main.py     random-walk entry point
```

Dependencies are strictly one-directional: `mrta → core`, `algo → core, mrta`,
`client → core`. `core/` never imports the others. See [`GUIDE.md`](GUIDE.md) for a
human tour of the project and [`AGENT.md`](AGENT.md) for the full architecture reference.

## Adding your own algorithm

Subclass `Coordinator` and implement `plan()`, returning a `PlanResult`:

```python
from core import Coordinator, PlanResult

class MyAlgo(Coordinator):
    def plan(self, agents, grid) -> PlanResult:
        positions = {a.agent_id: a.position for a in agents}   # your logic here
        moves = {a.agent_id: (a.position, positions[a.agent_id]) for a in agents}
        return PlanResult(positions=positions, moves=moves)
```

Then wire it in: `Simulation(grid, coordinator=MyAlgo())`. See
[`algo/coordination/random_walk.py`](algo/coordination/random_walk.py) for a minimal
working example.

## License

[MIT](LICENSE) © 2026 Arcko5
