import csv
from abc import ABC, abstractmethod
from pathlib import Path

from .run_record import RunRecord


class ResultSink(ABC):
    """Where a finished experiment goes.

    One method, so a CSV file and a database are interchangeable at the call
    site: ``main.py`` records a RunRecord and never learns which it got. A
    SQL implementation is a subclass with the same signature — it needs no
    change anywhere else, which is the whole point of the seam.
    """

    @abstractmethod
    def append(self, record: RunRecord) -> None:
        """Input: a finished run.
        Output: None. Persists it. Must be safe to call on an existing store.
        """
        ...


class CsvSink(ResultSink):
    """Appends one row per experiment to a CSV file.

    The header is written only when the file is created. On an existing file
    the stored header is compared against the record's fields and a mismatch
    **raises** instead of appending: a schema that gained a column mid-dataset
    would otherwise shift every later value one place to the left, producing a
    file that still parses and is quietly wrong. Failing here is the cheap
    outcome; discovering it during analysis is not.
    """

    def __init__(self, path: str | Path) -> None:
        """Input: the CSV path (created on first append).
        Output: None.
        """
        self.path = Path(path)

    def append(self, record: RunRecord) -> None:
        """Input: a finished run.
        Output: None. Appends one row, writing the header if the file is new.
        """
        columns = RunRecord.columns()
        exists = self.path.exists() and self.path.stat().st_size > 0

        if exists:
            self._check_header(columns)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            if not exists:
                writer.writeheader()
            writer.writerow(record.as_row())

    def _check_header(self, columns: list[str]) -> None:
        """Input: the expected column names.
        Output: None. Raises ValueError if the file's header differs.
        """
        with self.path.open(newline="") as handle:
            stored = next(csv.reader(handle), [])
        if stored == columns:
            return

        missing = [c for c in columns if c not in stored]
        extra = [c for c in stored if c not in columns]
        raise ValueError(
            f"{self.path} was written with a different schema and appending "
            f"would misalign every column.\n"
            f"  new fields: {missing or 'none'}\n"
            f"  dropped   : {extra or 'none'}\n"
            f"Use --results with a new file, or migrate the existing one."
        )


class NullSink(ResultSink):
    """Discards records — for runs that should not be logged."""

    def append(self, record: RunRecord) -> None:
        """Input: a finished run. Output: None. Does nothing."""
