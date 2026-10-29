from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from typing import Any

from app.services.profile_model import DatasetProfile

SCHEMA_VERSION = "1.0.0"


def serialize_profile_json(
    profile: DatasetProfile,
    *,
    datasetpeek_version: str,
    generated_at: datetime | None = None,
) -> str:
    """Serialize a profile into the public profile-model JSON contract."""

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)

    source_name = profile.file_summary.filename
    export_name = _export_filename(source_name)

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "datasetpeek_version": datasetpeek_version,
            "generated_at": _isoformat_utc(timestamp),
        },
        "file": {
            "filename": export_name,
            "file_type": profile.file_summary.file_type,
            "rows": profile.file_summary.rows,
            "columns": profile.file_summary.columns,
            "read_time_ms": profile.file_summary.read_time_ms,
        },
        "columns": [
            {
                "name": column.name,
                "dtype": column.dtype,
                "role": column.role,
                "non_null_ratio": column.non_null_ratio,
                "missing_ratio": column.missing_ratio,
                "unique_count": column.unique_count,
                "top_values": [
                    {
                        "value": top_value.value,
                        "count": top_value.count,
                        "ratio": top_value.ratio,
                    }
                    for top_value in column.top_values
                ],
            }
            for column in profile.columns
        ],
        "numeric_summary": [
            {
                "name": column.name,
                "min": _json_number(column.min),
                "max": _json_number(column.max),
                "mean": _json_number(column.mean),
                "median": _json_number(column.median),
            }
            for column in profile.numeric_columns
        ],
        "signals": [
            {
                "column": signal.column,
                "kind": signal.kind,
                "message": _sanitize(signal.message, source_name, export_name),
            }
            for signal in profile.signals
        ],
        "orientation": [
            _sanitize(item, source_name, export_name) for item in profile.orientation
        ],
        "next_checks": [
            _sanitize(item, source_name, export_name) for item in profile.next_checks
        ],
    }
    return json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _isoformat_utc(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def _export_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or filename


def _sanitize(text: str, source_name: str, export_name: str) -> str:
    if source_name and source_name != export_name:
        return text.replace(source_name, export_name)
    return text


def _json_number(value: int | float | Decimal | None) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (int, float)):
        return value
    return None
