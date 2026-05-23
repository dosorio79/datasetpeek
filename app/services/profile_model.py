from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FileSummary:
    filename: str
    file_type: str
    rows: int
    columns: int
    read_time_ms: int


@dataclass(frozen=True, slots=True)
class TopValue:
    value: str
    count: int
    pct: str


@dataclass(frozen=True, slots=True)
class ColumnSignal:
    column: str
    kind: str
    message: str


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    name: str
    dtype: str
    role: str
    non_null_pct: str
    missing_pct: str
    unique_count: int
    sample_values: list[str]
    top_values: list[TopValue] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class NumericColumnSummary:
    name: str
    min: str
    max: str
    mean: str
    median: str


@dataclass(frozen=True, slots=True)
class SampleSet:
    label: str
    rows: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    file_summary: FileSummary
    warnings: list[str]
    signals: list[ColumnSignal]
    columns: list[ColumnProfile]
    numeric_columns: list[NumericColumnSummary]
    sample_rows: list[dict[str, str]]
    sample_sets: list[SampleSet]
    sample_columns: list[str]
    head_rows: list[dict[str, str]]
    tail_rows: list[dict[str, str]]
    orientation: list[str]
    next_checks: list[str]
    markdown_report: str = ""
    html_report: str = ""
