from __future__ import annotations

from datetime import datetime, timezone
import json
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
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)

    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "datasetpeek_version": datasetpeek_version,
            "generated_at": _isoformat_utc(timestamp),
        },
        "file": {
            "filename": profile.file_summary.filename,
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
                "min": column.min,
                "max": column.max,
                "mean": column.mean,
                "median": column.median,
            }
            for column in profile.numeric_columns
        ],
        "signals": [
            {
                "column": signal.column,
                "kind": signal.kind,
                "message": signal.message,
            }
            for signal in profile.signals
        ],
        "orientation": list(profile.orientation),
        "next_checks": list(profile.next_checks),
    }
    return json.dumps(document, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _isoformat_utc(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")
