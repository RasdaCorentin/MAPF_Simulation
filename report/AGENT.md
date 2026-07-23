# report/ — the experiment log

> **Package guide.** The general context — layout, dependency direction, hard rules,
> invariants and the diagrams — lives in the root [`AGENT.md`](../AGENT.md) and is **not**
> repeated here. Read it first.

`report/` turns a run into one row. It is **opt-in**: without `main.py --log` no collector is
built at all and the frontend drives the `SimulationController` directly. Its only seams into
the rest of the project are `SimulationDriver` and the `StepSnapshot` it measures — it stays
out of the main class diagram and has [its own](../diagrammes/report_diagram.puml).

```python
@dataclass(frozen=True)
class RunRecord:                    # report/run_record.py — THE schema
    run_id, timestamp, schema_version, git_rev, label      # identity
    width, height, agents, obstacles, algo, mode, task_source, seed,
    patience, max_attempts                                  # scenario
    steps, wall_ms, step_ms_mean                            # run
    tasks_created/done/failed/unfinished, completion_rate,
    failed_unreachable, failed_stalled, reassignments, attempts_max
    wait_mean/max, service_mean/max, detour_mean/max         # latency
    drift_agents, drift_mean, drift_max, displaced_events, goalless_frac
    busy_frac, idle_max
    columns() -> list[str] ; as_row() -> dict ; sql_create_table(table) -> str

class ResultSink(ABC):              # report/sink.py
    append(record: RunRecord)
class CsvSink(ResultSink)           # appends; header written once
class NullSink(ResultSink)          # discards

class RunCollector(SimulationDriver):   # report/collector.py
    RunCollector(driver, config, label="")
    step() / run(steps)             # forwards to the wrapped driver, measuring
    snapshot() / send_batch_to()    # forwarded verbatim
    record(label=None) -> RunRecord
```

- **Every field is a plain scalar.** A CSV header and a SQL table are two renderings of the same
  record; anything nested would serialise to CSV and then have nowhere to go in a relational
  column. `sql_create_table()` lives next to the dataclass so the relational shape cannot drift
  from it, and resolves types through `typing.get_type_hints` rather than by parsing annotation
  text — guessing from the repr silently mistypes exactly the `Optional` columns.
- **`RunCollector` decorates the controller, it does not extend it** — but both implement
  `SimulationDriver` (`client/control/driver.py`), which is what makes the substitution a
  checked contract rather than `__getattr__` luck: a missing member now fails at instantiation
  instead of at the first click. It measures the **frame, not the engine**: every figure comes
  from the `StepSnapshot` that `step()` already returns, so the metrics can be reworked — and
  they will be — without the engine or the fleet changing. Reaching for the live `Simulation`
  and `FleetManager` would have been defensible (measuring is a stronger claim than drawing);
  it is simply not necessary, since a frame carries the task states, the goals and every
  agent's position.
- **`record()` reads the last *observed* frame**, not a fresh one. Every transition it reports
  was derived from that frame — `failed_unreachable` in particular is the part of `failed` no
  live task accounted for — so re-asking the driver would date the totals a tick later than the
  transitions explaining them, and the row would stop adding up.
- **Measurement is opt-in.** `report/` is still being validated, so it stays off the nominal
  path: without `--log` no collector is built and the frontend drives the controller itself.
  Either way the class diagram's `Frontend o-- SimulationDriver` holds.
- **Appending to a changed schema raises.** A new column would otherwise shift every later value
  one place left, producing a file that still parses and is quietly wrong. `schema_version` is
  stored on every row so a dataset spanning code changes stays interpretable; `git_rev` and
  `seed` are what make a row reproducible after the fact.
- **The run is logged in a `finally`**, so a window closed by hand or a Ctrl-C still records an
  observation; a logging failure is reported without masking the reason the run ended.

Swapping in SQL later means one new `ResultSink` subclass and nothing else — verified by loading
a `--log` CSV into sqlite with `sql_create_table()` unedited.

---
