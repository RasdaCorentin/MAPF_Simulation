# TODO

## Nothing in the repo runs end to end right now

Two removals, same reasoning each time: strip the concrete layer, leave only the pure
abstractions (`core`'s `PathPlanner`/`MissionOrchestrator`), force a deliberate redesign later
instead of letting the concrete stuff keep quietly justifying itself. A third, separate removal
dropped `mrta/` (task allocation) itself, and `sim_many_mrta.py` with it — out of scope for this
repository now, not merely broken.

### `main.py` — broken by the `client/`/`report/` removal

(`4f8aef4 refactor!: remove client/ and report/`)

`main.py` imports `client.control.{ScenarioConfig, build}` and `report.{CsvSink, RunCollector}`.
Both packages are gone. Running it now raises `ImportError` at the top-level import, before
anything else runs.

**Why it was not patched instead of fixed properly:** `client.control.build()` was the
project's one composition root (the only place naming a concrete `PathPlanner` and wiring the
scenario); `report.RunCollector` was the only thing measuring a run. Neither has a replacement
yet, and inlining a quick substitute into this script — or extracting one more shared helper
module — would just reintroduce a small `client` by another name without thinking through the
same question that led to this refactor: what should a caller-facing surface actually look like,
what stays private, what's public. That design conversation is intentionally still open; see the
project's own notes for it.

### `sim_many_pibt.py`, `sim_many_lacam.py`, `sim_many_pibt_plus.py` — broken by the `algo/` removal

(`9f2d15c refactor!: remove algo/`)

All three imported a concrete `Coordinator` directly from `algo.coordination`
(`PIBTCoordinator`, `LaCAMCoordinator`, `PIBTPlusCoordinator`) — none of it exists anymore.
Same `ImportError`-at-top-level failure mode as above. These three were, until this removal,
the only working entry points left in the repo and the de-facto regression checks — there are
now none.

**Why not patched either:** same reasoning as `client/`/`report/` above, one level down —
`algo/` was the only package with a concrete `Coordinator` (PIBT, LaCAM, PIBT+, random walk)
and the only concrete `Allocator` implementations (`EasiestAllocator`, `RandomAllocator`,
the already-stubbed `KDTreeGreedyAllocator`). Rewriting a coordinator inline in a benchmark
script to unblock it would be deciding the algorithm's shape as a side effect of unblocking a
script, not as its own considered piece of work.

### What unblocking any of this actually needs

1. At least one concrete `PathPlanner` again — `core/` still declares the abstraction
   (`PathPlanner`, `MissionOrchestrator`) untouched by either removal, there is simply nothing
   left that implements it. Task allocation (`mrta/`, `MissionOrchestrator`'s one-time concrete
   side) is gone from the repository, not just unimplemented — reintroducing it is a separate
   decision, not a side effect of unblocking a script.
2. A way to wire a `Grid2D` + `Agent`s + that `PathPlanner` — this used to be
   `client.control.factory.build()`; whatever replaces it should be scoped deliberately, not
   reconstructed as a byproduct of unblocking one script.
3. If run measurement (`--log`, `RunRecord`, the CSV outputs) is still wanted, a replacement
   for `report/RunCollector` that observes `WorldEngine` directly instead of a
   `SimulationDriver`/`StepSnapshot` it no longer has to decorate.

None of this should be done piecemeal inside `main.py`/`sim_many_*.py` ahead of the design
conversation these two removals were meant to force — that is exactly how the previous
`client/` accreted the way it did.
