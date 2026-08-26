# export/ — concrete Exporters

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`export/` supplies concrete `Exporter` implementations. It imports only from `core` and is one of
`core/`'s two dependents (alongside `pibt/`); the two never import each other — `export/` is
planner-agnostic, it works with whatever `PathPlanner` produced the run. The `Exporter` seam
itself lives in `core/engine/exporter.py`, not here — see `core/AGENT.md`. `record()` takes
`(step, agents, grid, outcome, intent)` — `intent` is the tick's `AssignmentManifest`, the same
object `planner.plan()` just consumed, not a copy fixed at construction.

### `TraceCsvExporter` — `export/trace_csv_exporter.py`
```python
class TraceCsvExporter(Exporter):
    def __init__(self, csv_path: str): ...
    def rows(self) -> list[tuple]: ...
    def record(self, step, agents, grid, outcome, intent) -> None: ...
    def flush(self) -> None: ...
```
The raw per-tick trace: one row per agent per tick (`step, agent_id, x, y, orientation`), read off
`agents` alone — `grid`, `outcome` and `intent` are all ignored. `flush()` writes it to `csv_path`
(e.g. `"log/trace/{date}.csv"`), creating parent directories on demand. `rows()` exposes the
accumulated rows read-only — `AggregateCsvExporter`'s data source, see below.

### `AggregateCsvExporter` — `export/aggregate_csv_exporter.py`
```python
class AggregateCsvExporter(Exporter):
    def __init__(self, csv_path: str, trace: TraceCsvExporter): ...
    def record(self, step, agents, grid, outcome, intent) -> None: ...
    def flush(self) -> None: ...
```
One CSV row per **run**, appended rather than overwritten — `csv_path`'s header is written only if
the file doesn't already exist, so successive runs accumulate in the same file.

`record()` reads only `intent.goals`, keyed by `(step, agent_id)` — not fixed at construction, so a
goal that changes mid-run (a lifelong `MissionOrchestrator` rotating goals) still counts a fresh
arrival per assignment, not just one per run. Position data is **not** re-read from `agents`: it
comes from the `TraceCsvExporter` given at construction, via `trace.rows()` — an explicit
intra-package coupling chosen over a second independent read of the same source. This means
`AggregateCsvExporter` cannot be used without a `TraceCsvExporter` instance (even one whose own
`.csv` output nobody looks at); `CompositeExporter.flush()` doesn't need to run them in any
particular order, since every exporter has already seen every tick's `record()` call by the time
any `flush()` runs — the coupling only matters at `AggregateCsvExporter.flush()`, once
`trace.rows()` is complete.

`flush()` computes, per agent, the tick of first arrival at its *currently assigned* goal (an
arrival is invalidated and re-armed whenever the goal changes), then appends one row: `date`,
`n_agents`, `ticks` (max step seen), `success_rate` (fraction of agents that arrived at least
once), `makespan` (latest arrival tick across agents, empty if none arrived), `deadlocks`
(agents that never arrived).

### `CompositeExporter` — `export/composite_exporter.py`
```python
class CompositeExporter(Exporter):
    def __init__(self, exporters: list[Exporter]): ...
    def record(self, step, agents, grid, outcome, intent) -> None: ...
    def flush(self) -> None: ...
```
Fans `record()`/`flush()` out to every wrapped `Exporter`, in order. `WorldEngine.exporter` still
holds exactly one object — this is that object, not a change to the seam itself: it's how one run
feeds both `TraceCsvExporter` and `AggregateCsvExporter` (or any other combination) at once.

`demo_trace_log.py` (`python3 demo_trace_log.py`) exercises `TraceCsvExporter` alone, writing a
timestamped trace under `log/trace/`. `demo_aggregate_log.py` (`python3 demo_aggregate_log.py`)
runs the same 3x3 scenario three times through
`CompositeExporter([TraceCsvExporter, AggregateCsvExporter])`, appending three rows to
`log/aggregate.csv`. `log/` is gitignored.
