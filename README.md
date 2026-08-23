# MAPF Simulation

A small **Multi-Agent Path Finding (MAPF)** simulator with a pluggable coordinator
interface, with no algorithm plugged in right now.

> **Currently just the abstractions, nothing runnable.** `core/` declares `Coordinator`
> and `Dispatcher`, but nothing implements either anymore — `algo/` (PIBT, LaCAM, PIBT+,
> random walk, the allocators), `mrta/` (task allocation) and `client/`/`report/` (scenario
> wiring, run measurement) were all removed on purpose, one after the other. See
> [`TODO.md`](TODO.md): nothing in the repo runs end to end today, including every
> `sim_many_*.py` sweep.

![Class diagram](diagrammes/Class_Diagram/simulation_class_diagram_commente.png)

## Inspiration & attribution

Until it was removed (see [`TODO.md`](TODO.md)), this project's PIBT coordinator was an
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
  returns a uniform `PlanResult` DTO. No concrete one is provided currently.
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

Nothing runs end to end right now — see [`TODO.md`](TODO.md) for the full picture. `core/`
still imports cleanly and can be exercised directly (construct a `Grid`/`Agent` by hand),
there is just no `Coordinator` implementation to run a full tick with.

## Project structure

```
core/       pure simulation engine — entities/ (Position, WorldEntity, Agent),
            environment/ (Grid), engine/ (Simulation, Coordinator, PlanResult)
diagrammes/ PlantUML class diagram sources + generated PNGs
main.py     CLI entry point — BROKEN, see TODO.md
```

`core/` has no dependents in the repository right now, and no outgoing dependencies of its
own. See [`GUIDE.md`](GUIDE.md) for a human tour of the project and [`AGENT.md`](AGENT.md)
for the full architecture reference.

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

Wire it in with a dispatcher that supplies the goals, e.g. a `StaticDispatcher` for fixed
targets:
`Simulation(grid, coordinator=MyAlgo(), dispatcher=StaticDispatcher(goals={...}))`. There is
currently no reference implementation left in the repo to copy the shape of — see
[`TODO.md`](TODO.md).

## License

[MIT](LICENSE) © 2026 Arcko5
