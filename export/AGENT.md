# export/ — concrete Exporters

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`export/` supplies concrete `Exporter` implementations. It imports only from `core` and is one of
`core/`'s two dependents (alongside `pibt/`); the two never import each other — `export/` is
planner-agnostic, it works with whatever `PathPlanner` produced the run. The `Exporter` seam
itself lives in `core/engine/exporter.py`, not here — see `core/AGENT.md`.

### `PlanVizExporter` — `export/planviz_exporter.py`
```python
class PlanVizExporter(Exporter):
    def __init__(self, map_path: str, plan_path: str, ticks_per_action: int = 1): ...
    def record(self, step: int, agents: list[Agent], grid: Grid2D, outcome: StepOutcome) -> None: ...
    def flush(self) -> None: ...
```
Writes a run in the format PlanViz (League of Robot Runners) reads: a `.map` file plus a `.json`
plan file (`start`, `actualPaths`, `plannerPaths`). Built from reading the Start-Kit's own export
code (`src/Simulator.cpp`, `src/ActionModel.cpp`, `inc/common.h`), not just
`Input_Output_Format.md`:

- **action vocabulary** — `F` (forward), `R` (rotate clockwise), `C` (rotate counter-clockwise),
  `W` (wait). Not a generic "rotate": `record()`'s `outcome.orientations` only ever carries the
  agent's *new* heading (`PIBTPlanner`'s `orientation=True` never enforces a rotate-XOR-move
  constraint — see the caveat on `Agent` in `core/AGENT.md`), so a same-tick position+orientation
  change becomes N clockwise-step `R`/`C` actions (whichever direction is fewer steps) followed by
  one `F` — one WorldEngine tick can become **two** PlanViz actions.
- **coordinates are `(row, col)`, not core's `(x, y)`** — a path segment header is
  `(tick, y, x, heading, 0)`. Matches the Start-Kit's row-major convention
  (`location = row*cols+col`), which happens to agree with `core`'s own axes (x East+, y South+)
  once transposed.
- **orientation has two encodings in the same file** — numeric (`E=0, S=1, W=2, N=3`) in a path
  segment header, but a *letter* (`Orientation.value` already matches) in the top-level `start`
  array. Not a bug to "fix" — that is genuinely how the Start-Kit writes it.
- **`ticks_per_action` defaults to `1`** — one PlanViz tick per WorldEngine tick. Does not model
  the Start-Kit's `agentCounter` (execution ticks per Forward/Rotate action, ~10 in the real
  competition); raising it replays every action `ticks_per_action` times for more realistic
  pacing in PlanViz's own player.

`record()`'s first call for a given agent also seeds a baseline entry from `outcome.moves` (the
`(from, to)` pair every `PathPlanner` fills), recovering the agent's pre-tick-1 position —
`WorldEngine` never calls `record()` before the first tick, so there is no other way to see it.
The baseline's *heading* is a throwaway placeholder: `flush()` defers the declared start heading
to the first real tick's heading instead of trusting `Agent`'s default `NORTH`, which is "nobody
told me yet," not an observed fact — an agent whose very first move is a straight line needs no
spurious rotate action to reach its "declared" starting heading.

`makespan` in the written plan is the sum of the encoded action durations, **not**
`WorldEngine.current_step`'s final value — they diverge whenever a same-tick rotate+move split
inserted an extra `R`/`C` action, so the exported timeline can run longer than the number of
WorldEngine ticks that produced it.

⚠ **Verified against a real scenario, not PlanViz itself.** A 3x3 grid, agent `(0,0) -> (2,2)`
under `PIBTPlanner(orientation=True)` was traced end to end and produces a correctly-encoded
`F 2,C 1,F 2` (the path turns a corner, exercising the split). PlanViz was not installed in the
environment this was built in (missing `pandas`) — the map/plan format is correct by
construction, but nobody has looked at it rendered yet.
