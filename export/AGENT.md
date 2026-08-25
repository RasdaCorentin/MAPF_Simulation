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

⚠ **Verified against real PlanViz, not just traced by hand.** A 3x3 grid, agent `(0,0) -> (2,2)`
under `PIBTPlanner(orientation=True)` — see `demo_planviz.py` — produces a correctly-encoded
`F 20,C 10,F 20` (`ticks_per_action=10`; the path turns a corner, exercising the split) and loads
into a real PlanViz install (`~/Inria/PlanViz`, `pip install -r requirements.txt` into a venv —
not part of this repo) correctly enough to render the map and the static path.

## Known gaps between a `core`/`pibt` run and PlanViz

Two `_write_plan()` workarounds for real PlanViz-loader defects, found by loading actual exported
output rather than guessing from the format doc:

- **`tasks` can never legitimately be empty.** `plan_config.py`'s `load_sequential_tasks()` only
  advances `max_seq_num` past its `-1` initial value by iterating a non-empty `"tasks"` list, and
  `load_events()` asserts `max_seq_num > -1` **unconditionally** — even when `"events"` is also
  empty, which it always is here (`core` has had no task/mission concept since `mrta` was
  removed). Loading a genuinely task-free run crashed on that assert. Fixed by always writing one
  zero-errand placeholder task, `[[0, 0, []]]`: satisfies the loader, `loc_num = len([])//2 = 0`
  means it renders nothing.
- **`agentMaxCounter` must be written explicitly, matching `ticks_per_action`.**
  `get_ticks_per_timestep()` defaults to `10` when the key is absent and interpolates one cell of
  motion across that many ticks; leaving `_ticks_per_action` at its own default of `1` without
  also writing `agentMaxCounter: 1` meant PlanViz assumed 10 ticks per cell while the export only
  ever supplied 1 — the agent visibly moved a few millimeters per action instead of a full cell,
  confirmed by manual testing. `_write_plan()` now always writes
  `"agentMaxCounter": self._ticks_per_action`, whatever that value is.

Three more gaps found by clicking around in the real UI, **not fixable from `export/` alone** —
each is either a second PlanViz-side defect or a direct structural consequence of `core`/`pibt`
having no task concept, not a bug in this package:

- **Play/Run crashes, and takes the rest of the transport controls down with it.** Pressing Play
  runs `move_agents_per_timestep()` (`plan_viz.py:3790`), which indexes
  `event_tracker["aTime"][event_tracker["aid"]]` with no bounds check. With zero real
  assigned-task events, `aTime` is just the `[-1]` sentinel `load_events()` appends; on the very
  first Play tick `cur_tstep` matches that `-1` by coincidence, `aid` increments to `1`, and the
  next access is out of range. The crash happens *after* Play's callback has already disabled
  Next/Prev/Restart/Go-to-timestep for the "running" state (mirroring the pattern at
  `plan_viz.py:896-902`) but *before* it would re-enable them on pause — so the whole transport
  freezes, not just auto-play. **Workaround: don't press Play.** Restarting PlanViz (not just the
  loaded plan) is the only way to unstick the controls once this fires.
- **Manual single-stepping is at raw execution-tick granularity, not per action.** Next/Prev
  advance one execution tick, and one grid-cell move takes `agentMaxCounter` ticks (10, to render
  visibly per the fix above) — a 6-cell path is on the order of 50-60 clicks with no "skip to next
  action boundary" control in the UI. This is the direct cost of fixing the millimeters-per-click
  problem above: the same granularity that makes motion *visible* also makes Next-only navigation
  tedious. Nothing in `export/` can change this without either PlanViz adding a
  skip-to-next-action control, or `core`/`pibt` gaining a real-time replanning loop with its own
  meaningful sub-cell states to display (neither exists).
- **Productivity shows nothing, ever — by construction, not a bug.** It plots
  `self.pcf.events["finished"]` (`get_finished_throughput_counts_by_time()`,
  `plan_viz.py:2389`), populated only from the JSON's `"events"` array. `_write_plan()` always
  writes `"events": []`: there is no task/errand-completion concept anywhere in `core`/`pibt` to
  report one from. Making Productivity show anything would mean deciding what a "task" or
  "errand" *is* for a plain point-to-point `PathPlanner` run with no `MissionOrchestrator` — e.g.
  synthesizing a fake completion event the moment an agent reaches its `OneShotGoalDispatcher`
  goal — which is a design decision about `export/`'s scope, not a bug fix; see
  `Class_Diagram/Export/` before writing any code for it.
