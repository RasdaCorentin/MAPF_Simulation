# TODO

## `main.py` and `sim_many_mrta.py` are currently broken

Both were left broken on purpose by the `client/`/`report/` removal (see
`4f8aef4 refactor!: remove client/ and report/`):

- `main.py` imports `client.control.{ScenarioConfig, build}` and `report.{CsvSink,
  RunCollector}`.
- `sim_many_mrta.py` imports `client.control.{ScenarioConfig, build, default_zones}` and
  `report.RunCollector`.

Both packages are gone. Running either script now raises `ImportError` at the top-level
import, before anything else runs.

**Why they were not patched instead of fixed properly:** `client.control.build()` was the
project's one composition root (the only place naming a concrete `Coordinator`/`Allocator`
and wiring `FleetManager`); `report.RunCollector` was the only thing measuring a run. Neither
has a replacement yet, and inlining a quick substitute into these two scripts — or extracting
one more shared helper module — would just reintroduce a small `client` by another name
without thinking through the same question that led to this refactor: what should a
caller-facing surface actually look like, what stays private, what's public. That design
conversation is intentionally still open; see the project's own notes for it.

**What unblocking these two actually needs:**
1. A way to wire a `Grid` + `Agent`s + `Coordinator` (+ `FleetManager` in MRTA mode) —
   `core/`, `algo/`, `mrta/` are all still there and untouched; `sim_many_pibt.py`,
   `sim_many_lacam.py` and `sim_many_pibt_plus.py` already do this by hand for the
   static/PIBT/LaCAM/PIBT+ case and are the closest working examples to copy the shape of for
   `main.py`. `sim_many_mrta.py` additionally needs the MRTA wiring (`QueueTaskSource`,
   `RandomTaskSource`, `EasiestAllocator`/`RandomAllocator`) that `client/control/factory.py`
   used to do — including `default_zones()`, which lived there too.
2. If run measurement (`--log`, `RunRecord`, the CSV outputs) is still wanted, a replacement
   for `report/RunCollector` that observes `Simulation`/`FleetManager` directly instead of a
   `SimulationDriver`/`StepSnapshot` it no longer has to decorate.

Neither of these should be done piecemeal inside `main.py`/`sim_many_mrta.py` ahead of that
design conversation — that is exactly how the previous `client/` accreted the way it did.
