from __future__ import annotations

from dataclasses import replace
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib
from typing import Any

import polars as pl

from app.services.file_reader import CSV_INCONSISTENT_ROWS_WARNING, UploadedFile
from app.services.heuristics import detect_column_role, detect_column_signals
from app.services.profile_model import (
    ColumnProfile,
    ColumnSignal,
    DatasetProfile,
    FileSummary,
    NumericColumnSummary,
    SampleSet,
    TopValue,
)
from app.services.settings import AppSettings, get_settings


def empty_view_model(*, error_message: str | None = None) -> dict[str, Any]:
    """Return the template context for the upload-first empty state."""

    settings = get_settings()
    return {
        "page_title": "DatasetPeek",
        "settings": settings,
        "error_message": error_message,
        "file_summary": None,
        "warnings": [],
        "signals": [],
        "columns": [],
        "numeric_columns": [],
        "orientation": [],
        "next_checks": [],
        "markdown_report": "",
        "html_report": "",
        "sample_rows": [],
        "sample_sets": [],
        "sample_columns": [],
        "head_rows": [],
        "tail_rows": [],
        "has_result": False,
    }


def build_profile_view_model(
    *,
    uploaded_file: UploadedFile,
    dataframe: pl.DataFrame,
    read_time_ms: int,
    warnings: list[str],
) -> dict[str, Any]:
    """Build the single-page profile context from a loaded dataset.

    This function is the product surface for the profiler: it keeps DatasetPeek to
    a fast first-contact summary, column signals, small previews, and no EDA UI.
    """

    profile = build_profile_model(
        uploaded_file=uploaded_file,
        dataframe=dataframe,
        read_time_ms=read_time_ms,
        warnings=warnings,
    )

    return {
        "page_title": "DatasetPeek",
        "settings": get_settings(),
        "error_message": None,
        "file_summary": {
            "filename": profile.file_summary.filename,
            "file_type": profile.file_summary.file_type,
            "rows": profile.file_summary.rows,
            "columns": profile.file_summary.columns,
            "read_time_ms": profile.file_summary.read_time_ms,
        },
        "warnings": profile.warnings,
        "signals": [_signal_dict(signal) for signal in profile.signals],
        "columns": [_column_dict(column) for column in profile.columns],
        "numeric_columns": [
            {
                "name": column.name,
                "min": column.min,
                "max": column.max,
                "mean": column.mean,
                "median": column.median,
            }
            for column in profile.numeric_columns
        ],
        "orientation": profile.orientation,
        "next_checks": profile.next_checks,
        "markdown_report": profile.markdown_report,
        "html_report": profile.html_report,
        "sample_rows": profile.sample_rows,
        "sample_sets": [{"label": sample.label, "rows": sample.rows} for sample in profile.sample_sets],
        "sample_columns": profile.sample_columns,
        "head_rows": profile.head_rows,
        "tail_rows": profile.tail_rows,
        "has_result": True,
    }


def build_profile_model(
    *,
    uploaded_file: UploadedFile,
    dataframe: pl.DataFrame,
    read_time_ms: int,
    warnings: list[str],
) -> DatasetProfile:
    """Build the structured first-contact profile used by UI and reports."""

    row_count = dataframe.height
    column_count = dataframe.width
    settings = get_settings()
    column_metrics, numeric_metrics = _collect_lazy_metrics(dataframe)
    columns: list[ColumnProfile] = []
    signals: list[ColumnSignal] = _warning_signals(warnings)
    numeric_columns: list[NumericColumnSummary] = []

    for series in dataframe.iter_columns():
        metrics = column_metrics[series.name]
        unique_count = metrics["unique_count"]
        missing_count = metrics["missing_count"]
        sample_values = _sample_values(series, settings=settings)
        role = detect_column_role(
            column_name=series.name,
            series=series,
            row_count=row_count,
            unique_count=unique_count,
            missing_count=missing_count,
        )
        columns.append(
            ColumnProfile(
                name=series.name,
                dtype=str(series.dtype),
                role=role,
                non_null_pct=_ratio_text(row_count - missing_count, row_count),
                missing_pct=_ratio_text(missing_count, row_count),
                unique_count=unique_count,
                sample_values=sample_values,
                top_values=_top_values(series, role=role, settings=settings),
            )
        )

        signals.extend(
            ColumnSignal(**signal)
            for signal in detect_column_signals(
                column_name=series.name,
                series=series,
                row_count=row_count,
                unique_count=unique_count,
                missing_count=missing_count,
            )
        )

        stats = numeric_metrics.get(series.name)
        if stats is not None:
            numeric_columns.append(NumericColumnSummary(name=series.name, **stats))

    sample_sets = _sample_sets(dataframe, settings=settings)
    sample_frame = sample_sets[0]["frame"] if sample_sets else dataframe.head(settings.random_sample_rows)
    formatted_sample_sets = [
        SampleSet(
            label=sample["label"],
            rows=_table_rows(sample["frame"], settings=settings),
        )
        for sample in sample_sets
    ]
    profile = DatasetProfile(
        file_summary=FileSummary(
            filename=uploaded_file.filename,
            file_type=uploaded_file.file_type.upper(),
            rows=row_count,
            columns=column_count,
            read_time_ms=read_time_ms,
        ),
        warnings=_size_warning(uploaded_file.content, settings=settings) + warnings,
        signals=signals,
        columns=columns,
        numeric_columns=numeric_columns,
        sample_rows=_table_rows(sample_frame, settings=settings),
        sample_sets=formatted_sample_sets,
        sample_columns=sample_frame.columns,
        head_rows=_table_rows(dataframe.head(settings.head_tail_rows), settings=settings),
        tail_rows=_table_rows(dataframe.tail(settings.head_tail_rows), settings=settings),
        orientation=[],
        next_checks=[],
    )
    profile = replace(
        profile,
        orientation=_orientation(profile),
        next_checks=_next_checks(profile),
    )
    return replace(
        profile,
        markdown_report=_markdown_report(profile),
        html_report=_html_report(profile),
    )


def _signal_dict(signal: ColumnSignal) -> dict[str, str]:
    return {
        "column": signal.column,
        "kind": signal.kind,
        "message": signal.message,
    }


def _warning_signals(warnings: list[str]) -> list[ColumnSignal]:
    signals: list[ColumnSignal] = []
    if CSV_INCONSISTENT_ROWS_WARNING in warnings:
        signals.append(
            ColumnSignal(
                column="Dataset",
                kind="CSV inconsistency",
                message="Some rows needed text parsing to keep the profile usable.",
            )
        )
    return signals


def _column_dict(column: ColumnProfile) -> dict[str, Any]:
    top_values = [
        {
            "value": top_value.value,
            "count": top_value.count,
            "pct": top_value.pct,
        }
        for top_value in column.top_values
    ]
    return {
        "name": column.name,
        "dtype": column.dtype,
        "role": column.role,
        "non_null_pct": column.non_null_pct,
        "missing_pct": column.missing_pct,
        "unique_count": column.unique_count,
        "sample_values": column.sample_values,
        "top_values": top_values,
        "top_values_text": _top_values_text(top_values),
    }


def _top_values(series: pl.Series, *, role: str, settings: AppSettings) -> list[TopValue]:
    if role not in {"Category", "Boolean flag", "Binary flag", "Numeric code"}:
        return []

    non_null = series.drop_nulls()
    non_null_count = len(non_null)
    if non_null_count == 0:
        return []

    value_counts = non_null.value_counts(sort=True).head(settings.top_values_limit)
    value_column = value_counts.columns[0]
    top_values: list[TopValue] = []
    for row in value_counts.iter_rows(named=True):
        count = int(row["count"])
        top_values.append(
            TopValue(
                value=_format_display_value(row[value_column], settings=settings),
                count=count,
                pct=_ratio_text(count, non_null_count),
            )
        )
    return top_values


def _orientation(profile: DatasetProfile) -> list[str]:
    columns_by_role = _columns_by_role(profile)
    items = [
        (
            f"{profile.file_summary.filename} is a {profile.file_summary.file_type} dataset with "
            f"{profile.file_summary.rows} rows and {profile.file_summary.columns} columns."
        )
    ]

    if identifiers := columns_by_role.get("Identifier"):
        items.append(f"Likely identifier columns: {_name_list(identifiers)}.")
    if flags := columns_by_role.get("Binary flag"):
        items.append(f"Binary flag columns: {_name_list(flags)}.")

    categorical_count = len(columns_by_role.get("Category", [])) + len(columns_by_role.get("Boolean flag", []))
    numeric_count = len(columns_by_role.get("Numeric measure", [])) + len(columns_by_role.get("Numeric code", []))
    if categorical_count or numeric_count:
        items.append(f"Detected {categorical_count} categorical/flag columns and {numeric_count} numeric columns.")

    quality_signals = [
        signal
        for signal in profile.signals
        if signal.kind
        in {
            "All missing",
            "Mostly missing",
            "Constant value",
            "Low variance",
            "Blank strings",
            "Suspicious mixed types",
            "High cardinality text",
            "CSV inconsistency",
        }
    ]
    if quality_signals:
        items.append(f"Quality risks to review: {_signal_list(quality_signals)}.")
    elif not profile.signals:
        items.append("No notable deterministic signals were detected.")

    return items[:5]


def _next_checks(profile: DatasetProfile) -> list[str]:
    columns_by_role = _columns_by_role(profile)
    checks: list[str] = []

    if columns_by_role.get("Identifier"):
        _append_unique(checks, "Verify identifier columns are unique and stable before joins.")
    if columns_by_role.get("Binary flag"):
        _append_unique(checks, "Confirm binary flag meaning and balance; decide whether any flag is an outcome.")
    if _has_signal(profile, {"All missing", "Mostly missing"}):
        _append_unique(checks, "Decide whether mostly or entirely missing columns should be dropped or imputed.")
    if _has_signal(profile, {"Suspicious mixed types", "Blank strings"}):
        _append_unique(checks, "Clean mixed-type or blank-string columns before modeling or joins.")
    if _has_signal(profile, {"CSV inconsistency"}):
        _append_unique(checks, "Review the CSV source rows that required text parsing before trusting inferred types.")
    if _has_signal(profile, {"High cardinality text"}):
        _append_unique(checks, "Inspect high-cardinality text before encoding, grouping, or search use.")
    if _has_signal(profile, {"Constant value", "Low variance"}):
        _append_unique(checks, "Review constant or low-variance columns; they may add little signal.")

    if not checks:
        checks.append("Review inferred roles and sample rows before downstream use.")

    return checks[:5]


def _markdown_report(profile: DatasetProfile) -> str:
    lines = [
        "# DatasetPeek Profile Report",
        "",
        f"DatasetPeek version: {_datasetpeek_version()}",
        "",
        "## File Summary",
        "",
        f"- Filename: {profile.file_summary.filename}",
        f"- Type: {profile.file_summary.file_type}",
        f"- Rows: {profile.file_summary.rows}",
        f"- Columns: {profile.file_summary.columns}",
        f"- Read time: {profile.file_summary.read_time_ms} ms",
        "",
        "## Orientation",
        "",
        *_markdown_list(profile.orientation),
        "",
        "## Signals",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["Column", "Signal", "Detail"],
            [[signal.column, signal.kind, signal.message] for signal in profile.signals],
            empty="No notable deterministic signals detected.",
        )
    )
    lines.extend(
        [
            "",
            "## Column Overview",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            ["Name", "Dtype", "Role", "Non-null %", "Missing %", "Unique", "Top values"],
            [
                [
                    column.name,
                    column.dtype,
                    column.role,
                    column.non_null_pct,
                    column.missing_pct,
                    str(column.unique_count),
                    _top_values_text(
                        [
                            {"value": value.value, "count": value.count, "pct": value.pct}
                            for value in column.top_values
                        ]
                    ),
                ]
                for column in profile.columns
            ],
        )
    )
    lines.extend(["", "## Numeric Summary", ""])
    lines.extend(
        _markdown_table(
            ["Name", "Min", "Max", "Mean", "Median"],
            [[column.name, column.min, column.max, column.mean, column.median] for column in profile.numeric_columns],
            empty="No numeric columns detected.",
        )
    )
    lines.extend(["", "## Next Checks", "", *_markdown_list(profile.next_checks), ""])
    return "\n".join(lines)


def _html_report(profile: DatasetProfile) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>DatasetPeek Profile Report</title>",
            "<style>",
            "body{font-family:Arial,sans-serif;line-height:1.45;margin:32px;color:#172026;background:#fff}",
            "h1,h2{color:#102a35}table{border-collapse:collapse;width:100%;margin:12px 0 24px}",
            "th,td{border:1px solid #d6dee3;padding:8px;text-align:left;vertical-align:top}",
            "th{background:#eef5f7}.muted{color:#5b6b73}",
            "</style>",
            "</head>",
            "<body>",
            "<h1>DatasetPeek Profile Report</h1>",
            f'<p class="muted">DatasetPeek version: {escape(_datasetpeek_version())}</p>',
            "<h2>File Summary</h2>",
            "<ul>",
            f"<li><strong>Filename:</strong> {escape(profile.file_summary.filename)}</li>",
            f"<li><strong>Type:</strong> {escape(profile.file_summary.file_type)}</li>",
            f"<li><strong>Rows:</strong> {profile.file_summary.rows}</li>",
            f"<li><strong>Columns:</strong> {profile.file_summary.columns}</li>",
            f"<li><strong>Read time:</strong> {profile.file_summary.read_time_ms} ms</li>",
            "</ul>",
            "<h2>Orientation</h2>",
            _html_list(profile.orientation),
            "<h2>Signals</h2>",
            _html_table(
                ["Column", "Signal", "Detail"],
                [[signal.column, signal.kind, signal.message] for signal in profile.signals],
                empty="No notable deterministic signals detected.",
            ),
            "<h2>Column Overview</h2>",
            _html_table(
                ["Name", "Dtype", "Role", "Non-null %", "Missing %", "Unique", "Top values"],
                [
                    [
                        column.name,
                        column.dtype,
                        column.role,
                        column.non_null_pct,
                        column.missing_pct,
                        str(column.unique_count),
                        _top_values_text(
                            [
                                {"value": value.value, "count": value.count, "pct": value.pct}
                                for value in column.top_values
                            ]
                        ),
                    ]
                    for column in profile.columns
                ],
            ),
            "<h2>Numeric Summary</h2>",
            _html_table(
                ["Name", "Min", "Max", "Mean", "Median"],
                [[column.name, column.min, column.max, column.mean, column.median] for column in profile.numeric_columns],
                empty="No numeric columns detected.",
            ),
            "<h2>Next Checks</h2>",
            _html_list(profile.next_checks),
            "</body>",
            "</html>",
        ]
    )


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


def _sample_sets(dataframe: pl.DataFrame, *, settings: AppSettings) -> list[dict[str, Any]]:
    """Return a small finite set of preview samples for client-side cycling."""

    if dataframe.height <= settings.random_sample_rows:
        return [{"label": "Full preview", "frame": dataframe}]

    seeds = (42, 43, 44, 45)
    return [
        {
            "label": f"Sample {index}",
            "frame": dataframe.sample(n=settings.random_sample_rows, shuffle=True, seed=seed),
        }
        for index, seed in enumerate(seeds, start=1)
    ]


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


def _format_display_value(value: Any, *, settings: AppSettings) -> str:
    formatted = _format_value(value)
    if formatted == "" and value is not None:
        formatted = "(blank)"
    return _truncate(formatted, settings=settings)


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
        f"Large file ({size_mb:.1f} MB). DatasetPeek accepts up to {settings.max_upload_mb} MB, "
        "but smaller files profile more reliably."
    ]


def _columns_by_role(profile: DatasetProfile) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for column in profile.columns:
        grouped.setdefault(column.role, []).append(column.name)
    return grouped


def _name_list(names: list[str], *, limit: int = 4) -> str:
    visible = names[:limit]
    suffix = f" and {len(names) - limit} more" if len(names) > limit else ""
    return ", ".join(visible) + suffix


def _signal_list(signals: list[ColumnSignal], *, limit: int = 4) -> str:
    labels = [f"{signal.column} ({signal.kind})" for signal in signals[:limit]]
    suffix = f" and {len(signals) - limit} more" if len(signals) > limit else ""
    return ", ".join(labels) + suffix


def _has_signal(profile: DatasetProfile, kinds: set[str]) -> bool:
    return any(signal.kind in kinds for signal in profile.signals)


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _top_values_text(top_values: list[dict[str, Any]]) -> str:
    if not top_values:
        return ""
    return ", ".join(f"{item['value']} ({item['count']}, {item['pct']})" for item in top_values)


def _markdown_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _markdown_table(headers: list[str], rows: list[list[str]], *, empty: str | None = None) -> list[str]:
    if not rows:
        return [empty or ""]
    escaped_headers = [_markdown_cell(header) for header in headers]
    lines = [
        "| " + " | ".join(escaped_headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_markdown_cell(cell) for cell in row) + " |")
    return lines


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _html_list(items: list[str]) -> str:
    if not items:
        return "<p>None</p>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _html_table(headers: list[str], rows: list[list[str]], *, empty: str | None = None) -> str:
    if not rows:
        return f"<p>{escape(empty or '')}</p>"
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _datasetpeek_version() -> str:
    try:
        return version("datasetpeek")
    except PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        try:
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except OSError:
            return "unknown"
        return str(data.get("project", {}).get("version", "unknown"))
