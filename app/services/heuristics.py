from __future__ import annotations

import re
from typing import Any

import polars as pl

BOOLEAN_SETS = (
    {"true", "false"},
    {"yes", "no"},
    {"y", "n"},
    {"1", "0"},
    {"t", "f"},
)
TARGET_BOOLEAN_SETS = (
    {"true", "false"},
    {"1", "0"},
)

ID_HINT_PATTERN = re.compile(r"(?:^|_)(id|key|code)(?:$|_)")
VALUE_COUNT_CANDIDATE_UNIQUE_RATIO = 0.10
NUMERIC_DISCRETE_MAX_UNIQUE = 10


def detect_column_signals(
    *,
    column_name: str,
    series: pl.Series,
    row_count: int,
    unique_count: int,
    missing_count: int,
) -> list[dict[str, Any]]:
    """Return high-signal column warnings for first-contact dataset review.

    The heuristics favor cheap, explainable checks over exhaustive profiling so
    the app remains an orientation tool instead of a full EDA report.
    """

    signals: list[dict[str, Any]] = []

    non_null = series.drop_nulls()
    non_null_count = len(non_null)
    if row_count == 0 or non_null_count == 0:
        return signals

    non_null_unique_count = non_null.n_unique()
    unique_ratio = unique_count / row_count if row_count else 0.0
    non_null_unique_ratio = non_null_unique_count / non_null_count if non_null_count else 0.0
    non_null_ratio = non_null_count / row_count if row_count else 0.0
    missing_ratio = missing_count / row_count if row_count else 0.0

    if missing_ratio > 0.50:
        signals.append(_signal(column_name, "Mostly missing", f"{missing_ratio:.1%} missing"))

    if _looks_like_id(column_name, series, non_null_unique_ratio, non_null_ratio):
        signals.append(_signal(column_name, "Possible ID", f"{non_null_unique_ratio:.1%} unique"))

    if _is_high_cardinality_text(series, unique_count, row_count):
        signals.append(_signal(column_name, "High cardinality text", f"{unique_count} distinct values"))

    is_boolean_like = _is_boolean_like(non_null)
    if is_boolean_like:
        signals.append(_signal(column_name, "Boolean disguised as string", "Values resemble yes/no, true/false, or 0/1"))

    if _has_mixed_types(non_null):
        signals.append(_signal(column_name, "Suspicious mixed types", "Contains both numeric-like and free-text values"))

    has_binary_signal = False
    if _needs_value_count_scan(unique_count=non_null_unique_count, unique_ratio=non_null_unique_ratio):
        value_counts = non_null.value_counts(sort=True)
        top_row = value_counts.row(0, named=True)
        top_value = top_row[series.name]
        top_frequency = int(top_row["count"])
        top_ratio = top_frequency / non_null_count if non_null_count else 0.0

        if top_ratio >= 0.95:
            signals.append(_signal(column_name, "Low variance", f'{top_value!r} appears {top_ratio:.1%}'))

        if non_null_unique_count == 2 and non_null_ratio >= 0.5 and _is_binary_target_domain(value_counts):
            signals.append(_signal(column_name, "Binary / target", _binary_message(value_counts, non_null_count)))
            has_binary_signal = True
        elif value_counts.height >= 2:
            top_two = value_counts.head(2)["count"].sum()
            if (
                (top_two / non_null_count) >= 0.98
                and non_null_ratio >= 0.5
                and _is_binary_target_domain(value_counts.head(2))
            ):
                signals.append(_signal(column_name, "Binary / target", _binary_message(value_counts.head(2), non_null_count)))
                has_binary_signal = True

    if not has_binary_signal and not is_boolean_like and _is_likely_categorical(series, unique_count, row_count):
        signals.append(_signal(column_name, "Likely categorical", f"{unique_count} distinct values"))

    if not has_binary_signal and _is_numeric_discrete(
        column_name=column_name,
        series=non_null,
        unique_count=non_null_unique_count,
        non_null_unique_ratio=non_null_unique_ratio,
    ):
        signals.append(_signal(column_name, "Possible numeric discrete", f"{non_null_unique_count} distinct integer values"))

    return signals


def _signal(column: str, kind: str, message: str) -> dict[str, str]:
    return {"column": column, "kind": kind, "message": message}


def _looks_like_id(column_name: str, series: pl.Series, unique_ratio: float, non_null_ratio: float) -> bool:
    """Detect likely row or entity identifiers from names and uniqueness."""

    has_id_name = bool(ID_HINT_PATTERN.search(column_name.lower()))
    if has_id_name:
        return True
    if non_null_ratio < 0.9:
        return False
    if unique_ratio < 0.98:
        return False
    return series.dtype.is_integer()


def _needs_value_count_scan(*, unique_count: int, unique_ratio: float) -> bool:
    """Limit value-count scans to columns likely to produce concise signals."""

    if unique_count <= 2:
        return True
    return unique_ratio <= VALUE_COUNT_CANDIDATE_UNIQUE_RATIO


def _binary_message(value_counts: pl.DataFrame, non_null_count: int) -> str:
    parts: list[str] = []
    for row in value_counts.iter_rows(named=True):
        value = row[value_counts.columns[0]]
        ratio = row["count"] / non_null_count if non_null_count else 0
        parts.append(f"{value}: {ratio:.1%}")
    return ", ".join(parts)


def _is_likely_categorical(series: pl.Series, unique_count: int, row_count: int) -> bool:
    """Detect compact string-like domains that help users orient quickly."""

    if series.dtype.is_numeric():
        return False
    unique_ratio = unique_count / row_count if row_count else 0
    if unique_ratio >= 0.5:
        return False
    return unique_count <= 20 or unique_ratio <= 0.05


def _is_high_cardinality_text(series: pl.Series, unique_count: int, row_count: int) -> bool:
    if series.dtype != pl.String:
        return False
    unique_ratio = unique_count / row_count if row_count else 0
    return unique_count >= 50 and unique_ratio >= 0.50


def _is_boolean_like(series: pl.Series) -> bool:
    if series.dtype != pl.String:
        return False
    normalized = {str(value).strip().lower() for value in series.unique().to_list() if str(value).strip()}
    return bool(normalized) and any(normalized <= candidate for candidate in BOOLEAN_SETS)


def _is_binary_target_domain(value_counts: pl.DataFrame) -> bool:
    normalized = {
        str(row[value_counts.columns[0]]).strip().lower()
        for row in value_counts.iter_rows(named=True)
        if str(row[value_counts.columns[0]]).strip()
    }
    return bool(normalized) and any(normalized <= candidate for candidate in TARGET_BOOLEAN_SETS)


def _has_mixed_types(series: pl.Series) -> bool:
    """Flag string columns that mix numeric-looking values with free text."""

    if series.dtype != pl.String:
        return False
    sample = [str(value).strip() for value in series.head(50).to_list() if str(value).strip()]
    if len(sample) < 3:
        return False

    numeric_like = sum(_looks_numeric(value) for value in sample)
    return 0 < numeric_like < len(sample)


def _looks_numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _is_numeric_discrete(
    *,
    column_name: str,
    series: pl.Series,
    unique_count: int,
    non_null_unique_ratio: float,
) -> bool:
    """Detect integer-coded categories without treating binary or ID columns as categorical."""

    if not series.dtype.is_integer():
        return False
    if unique_count < 3 or unique_count > NUMERIC_DISCRETE_MAX_UNIQUE:
        return False
    if non_null_unique_ratio >= 0.90:
        return False
    if bool(ID_HINT_PATTERN.search(column_name.lower())):
        return False
    return True
