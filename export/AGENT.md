# export/ — concrete Exporters

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`export/` supplies concrete `Exporter` implementations. It imports only from `core` and is one of
`core/`'s two dependents (alongside `pibt/`); the two never import each other — `export/` is
planner-agnostic, it works with whatever `PathPlanner` produced the run. The `Exporter` seam
itself lives in `core/engine/exporter.py`, not here — see `core/AGENT.md`.

### `CsvExporter` — `export/csv_exporter.py`
```python
class CsvExporter(Exporter):
    def __init__(self, csv_path: str): ...
    def record(self, step: int, agents: list[Agent], grid: Grid2D, outcome: StepOutcome) -> None: ...
    def flush(self) -> None: ...
```
Accumulates `(position, orientation)` per agent per tick in memory; `flush()` writes one flat CSV
with a header row (`step, agent_id, x, y, orientation`) and one row per agent per tick, to the
`csv_path` given at construction — parent directories are created on demand, so passing something
like `"log/run.csv"` just works. No external viewer format to satisfy: the columns are `core`'s own
axes and `Orientation.name`, nothing transposed or re-encoded.

`demo_csv_log.py` (`python3 demo_csv_log.py`) wires `CsvExporter` to a 3x3 `PIBTPlanner` run and
writes `log/demo_3x3.csv`; `log/` is gitignored, same role `runs/` played before.
