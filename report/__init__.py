"""Experiment logging: measure a run, persist it, keep it queryable later.

    RunRecord   — the schema: one experiment, flat scalars only
    ResultSink  — where a record goes (CsvSink now, a SQL sink later)
    RunCollector— decorates a SimulationController and measures it

Depends on ``core`` and ``mrta`` for value types; it observes a controller
through public attributes only, so the metrics can be reworked without the
engine or the fleet having to change.
"""

from .run_record import RunRecord, SCHEMA_VERSION
from .sink import ResultSink, CsvSink, NullSink
from .collector import RunCollector

__all__ = [
    "RunRecord", "SCHEMA_VERSION",
    "ResultSink", "CsvSink", "NullSink",
    "RunCollector",
]
