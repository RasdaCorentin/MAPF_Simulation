# Project guide — MAPF Simulation

A friendly tour of the project: what it is, how to run it, how the pieces fit, and
where to look when you want to change something. For the exhaustive class-by-class
reference, see [`AGENT.md`](AGENT.md); for git conventions, see
[`CONVENTION.md`](CONVENTION.md).

---

## What is this?

A small **Multi-Agent Path Finding (MAPF)** simulator. Several agents live on a grid,
each wants to reach a goal cell, and a **`PathPlanner`** decides — every step — where
everyone moves so that no two agents collide. `core/` declares that interface but, as of
this refactor, provides no implementation of it — see [`TODO.md`](TODO.md) for why and
what used to be there (PIBT, LaCAM, PIBT+, random walk).

There used to be an optional **task-allocation** layer on top of the movement layer
(`mrta/`): tasks appearing over time, matched to free agents, their targets pushed to the
planner as goals. It was removed — task allocation is out of scope for this repository
now; see [`TODO.md`](TODO.md).

---

## Quickstart

```bash
# (optional) virtual environment
python -m venv .venv && source .venv/bin/activate
```

Nothing currently runs end to end — `main.py` and every `sim_many_*.py` sweep are broken,
see [`TODO.md`](TODO.md) for the full picture. `core/` still imports cleanly and can be
exercised directly from a Python shell (construct a `Grid2D`, an `Agent` by hand); there is
just no `PathPlanner` to run a full tick with.

No runtime dependencies are needed (`requirements.txt` is currently empty).

---

## How it fits together

One package left, no dependents:

- **`core/`** — the pure engine, no rendering, no algorithm. Holds the world:
  `Coordinates2D`, `WorldEntity`, `Orientation`, `Agent`, `Objective`, `Grid2D`, the
  `WorldEngine` loop, and the `PathPlanner` interface plus its `StepOutcome` return type.

There used to be two other packages: `algo/` (the algorithms: PIBT, LaCAM, PIBT+, random
walk, the allocators) and `mrta/` (task allocation: `Mission`, mission sources, an
allocation strategy, `TaskDrivenOrchestrator`, which handed goals to the planner), plus a
scripting layer above both to wire a scenario. All were removed deliberately — see
[`TODO.md`](TODO.md) for why and what's needed to bring any of it back.

The key handshake: `WorldEngine.advance_time_step()` asks the planner to `plan()` and gets
back a `StepOutcome` (next positions + diagnostics).

For the visual overview, see the class diagram:

![Class diagram](diagrammes/Class_Diagram/simulation_class_diagram_commente.png)

---

## Where to look for X

| I want to…                                   | Go to…                                          |
|:---------------------------------------------|:------------------------------------------------|
| Add a planner (none exist right now)         | subclass `PathPlanner` from `core`, see "Extending it" below |
| Change the grid, entities, or the step loop  | `core/`                                          |
| Update the class diagram                     | `diagrammes/Class_Diagram/class_diag_commented.puml` (+ `plantuml`) |

---

## Extending it

**A new planner** — subclass `PathPlanner`, implement `plan()`, return a `StepOutcome`:

```python
from core import PathPlanner, StepOutcome

class MyAlgo(PathPlanner):
    def plan(self, agents, grid, intent) -> StepOutcome:
        positions = {a.agent_id: a.position for a in agents}   # your logic here
        moves = {a.agent_id: (a.position, positions[a.agent_id]) for a in agents}
        return StepOutcome(positions=positions, moves=moves)
```

Plug it in with `WorldEngine(grid, planner=MyAlgo())`. There is currently no reference
implementation left in the repo to copy the shape of — `algo/` (PIBT, LaCAM, PIBT+, random
walk) was removed; see [`TODO.md`](TODO.md).

---

## Documentation map

| File            | Audience   | Purpose                                            |
|:----------------|:-----------|:---------------------------------------------------|
| `README.md`     | everyone   | short overview, install, run                       |
| `GUIDE.md`      | humans     | this guided tour                                   |
| `AGENT.md`      | agents/devs| exhaustive per-class architecture reference        |
| `CONVENTION.md` | contributors | git, branch, commit and issue conventions        |
