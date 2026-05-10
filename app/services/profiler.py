from __future__ import annotations

from typing import Any

import polars as pl

from app.services.file_reader import UploadedFile
from app.services.heuristics import detect_column_signals
from app.services.settings import AppSettings, get_settings


def empty_view_model(*, error_message: str | None = None) -> dict[str, Any]:
    """Return the template context for the upload-first empty state."""

    settings = get_settings()
    return {
        "page_title": "DataPeek",
        "settings": settings,
        "error_message": error_message,
        "file_summary": None,
        "warnings": [],
        "signals": [],
        "columns": [],
        "numeric_columns": [],
        "sample_rows": [],
        "sample_columns": [],
        "head_rows": [],
        "tail_rows": [],
        "upload_token": "",
        "next_resample_seed": 43,
        "has_result": False,
    }


def build_profile_view_model(
    *,
    uploaded_file: UploadedFile,
    dataframe: pl.DataFrame,
    read_time_ms: int,
    warnings: list[str],
    upload_token: str,
    sample_seed: int,
) -> dict[str, Any]:
    """Build the single-page profile context from a loaded dataset.

    This function is the product surface for the profiler: it keeps DataPeek to
    a fast first-contact summary, column signals, small previews, and no EDA UI.
    """

    row_count = dataframe.height
    column_count = dataframe.width
    settings = get_settings()
    column_metrics, numeric_metrics = _collect_lazy_metrics(dataframe)
    columns: list[dict[str, Any]] = []
    signals: list[dict[str, str]] = []
    numeric_columns: list[dict[str, Any]] = []

    for series in dataframe.iter_columns():
        metrics = column_metrics[series.name]
        unique_count = metrics["unique_count"]
        missing_count = metrics["missing_count"]
        sample_values = _sample_values(series, settings=settings)
        columns.append(
            {
                "name": series.name,
                "dtype": str(series.dtype),
                "non_null_pct": _ratio_text(row_count - missing_count, row_count),
                "missing_pct": _ratio_text(missing_count, row_count),
                "unique_count": unique_count,
                "sample_values": sample_values,
            }
        )

        signals.extend(
            detect_column_signals(
                column_name=series.name,
                series=series,
                row_count=row_count,
                unique_count=unique_count,
                missing_count=missing_count,
            )
        )

        stats = numeric_metrics.get(series.name)
        if stats is not None:
            numeric_columns.append({"name": series.name, **stats})

    sample_frame = _sample_frame(dataframe, sample_seed, settings=settings)
    return {
        "page_title": "DataPeek",
        "settings": settings,
        "error_message": None,
        "file_summary": {
            "filename": uploaded_file.filename,
            "file_type": uploaded_file.file_type.upper(),
            "rows": row_count,
            "columns": column_count,
            "read_time_ms": read_time_ms,
        },
        "warnings": _size_warning(uploaded_file.content, settings=settings) + warnings,
        "signals": signals,
        "columns": columns,
        "numeric_columns": numeric_columns,
        "sample_rows": _table_rows(sample_frame, settings=settings),
        "sample_columns": sample_frame.columns,
        "head_rows": _table_rows(dataframe.head(settings.head_tail_rows), settings=settings),
        "tail_rows": _table_rows(dataframe.tail(settings.head_tail_rows), settings=settings),
        "upload_token": upload_token,
        "next_resample_seed": sample_seed + 1,
        "has_result": True,
    }


def _sample_values(series: pl.Series, *, settings: AppSettings) -> list[str]:
    """Return a tiny representative value set for the column overview table."""

    values = series.drop_nulls().unique(maintain_order=True).head(settings.sample_value_count).to_list()
    return [_truncate(_format_value(value), settings=settings) for value in values]


def _collect_lazy_metrics(dataframe: pl.DataFrame) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, str]]]:
    # The upload is already an in-memory DataFrame, but lazy execution still helps:
    # we can batch cheap aggregates into one optimized Polars plan instead of
    # triggering a separate eager aggregation for every column inside Python.
    lazy_frame = dataframe.lazy()
    summary_expressions: list[pl.Expr] = []

    for column_name in dataframe.columns:
        column = pl.col(column_name)
        summary_expressions.append(column.null_count().alias(f"{column_name}__missing"))
        summary_expressions.append(column.n_unique().alias(f"{column_name}__unique"))

    numeric_columns = [series.name for series in dataframe.iter_columns() if series.dtype.is_numeric()]
    for column_name in numeric_columns:
        column = pl.col(column_name)
        summary_expressions.extend(
            (
                column.min().alias(f"{column_name}__min"),
                column.max().alias(f"{column_name}__max"),
                column.mean().alias(f"{column_name}__mean"),
                column.median().alias(f"{column_name}__median"),
            )
        )

    if not summary_expressions:
        return {}, {}

    summary_row = lazy_frame.select(summary_expressions).collect().row(0, named=True)
    column_metrics = {
        column_name: {
            "missing_count": int(summary_row[f"{column_name}__missing"]),
            "unique_count": int(summary_row[f"{column_name}__unique"]),
        }
        for column_name in dataframe.columns
    }
    numeric_metrics = {
        column_name: {
            "min": _format_value(summary_row[f"{column_name}__min"]),
            "max": _format_value(summary_row[f"{column_name}__max"]),
            "mean": _format_value(summary_row[f"{column_name}__mean"]),
            "median": _format_value(summary_row[f"{column_name}__median"]),
        }
        for column_name in numeric_columns
    }
    return column_metrics, numeric_metrics


def _sample_frame(dataframe: pl.DataFrame, sample_seed: int, *, settings: AppSettings) -> pl.DataFrame:
    """Return the preview sample, capped by runtime settings."""

    if dataframe.height <= settings.random_sample_rows:
        return dataframe
    return dataframe.sample(n=settings.random_sample_rows, shuffle=True, seed=sample_seed)


def _table_rows(dataframe: pl.DataFrame, *, settings: AppSettings) -> list[dict[str, str]]:
    """Format a Polars frame for compact HTML table rendering."""

    rows: list[dict[str, str]] = []
    for row in dataframe.iter_rows(named=True):
        rows.append({column: _truncate(_format_value(value), settings=settings) for column, value in row.items()})
    return rows


def _ratio_text(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0%"
    return f"{(numerator / denominator):.1%}"


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _truncate(value: str, *, settings: AppSettings) -> str:
    max_length = settings.text_truncate_chars
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1]}…"


def _size_warning(content: bytes, *, settings: AppSettings) -> list[str]:
    if len(content) <= settings.large_file_warning_bytes:
        return []
    size_mb = len(content) / (1024 * 1024)
    return [
        f"Large file ({size_mb:.1f} MB). DataPeek accepts up to {settings.max_upload_mb} MB, "
        "but smaller files profile more reliably."
    ]
