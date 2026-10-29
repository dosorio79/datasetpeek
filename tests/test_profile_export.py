from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json

import polars as pl

from app.services.file_reader import UploadedFile
from app.services.profile_export import serialize_profile_json
from app.services.profiler import build_profile_model


def make_profile():
    uploaded_file = UploadedFile(
        filename="metrics.csv",
        content=b"measure,group\n0.123456789,a\n0.987654321,a\n,b\n,b\n,b\n,b\n,b\n,b\n,b\n,b\n",
        file_type="csv",
    )
    dataframe = pl.DataFrame(
        {
            "measure": [0.123456789, 0.987654321, None, None, None, None, None, None, None, None],
            "group": ["a", "a", "b", "b", "b", "b", "b", "b", "b", "b"],
        }
    )
    profile = build_profile_model(
        uploaded_file=uploaded_file,
        dataframe=dataframe,
        read_time_ms=7,
        warnings=[],
    )
    return replace(
        profile,
        sample_rows=[{"measure": "sample-only-secret"}],
        head_rows=[{"measure": "sample-only-secret"}],
        tail_rows=[{"measure": "sample-only-secret"}],
        columns=[
            replace(column, sample_values=["sample-only-secret"])
            for column in profile.columns
        ],
    )


def test_export_json_has_versioned_numeric_schema_and_excludes_previews(monkeypatch):
    monkeypatch.setenv("DATASETPEEK_TOP_VALUES_LIMIT", "1")
    profile = make_profile()
    timestamp = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)

    exported = json.loads(
        serialize_profile_json(profile, datasetpeek_version="0.5.0", generated_at=timestamp)
    )

    assert exported["schema_version"] == "1.0.0"
    assert exported["metadata"] == {
        "datasetpeek_version": "0.5.0",
        "generated_at": "2026-10-29T12:00:00Z",
    }
    assert [column["name"] for column in exported["columns"]] == ["measure", "group"]
    measure = next(column for column in exported["columns"] if column["name"] == "measure")
    assert measure["non_null_ratio"] == 2 / 10
    assert measure["missing_ratio"] == 8 / 10
    group = next(column for column in exported["columns"] if column["name"] == "group")
    assert len(group["top_values"]) == 1
    assert isinstance(group["top_values"][0]["count"], int)
    assert isinstance(group["top_values"][0]["ratio"], float)
    numeric = exported["numeric_summary"][0]
    assert isinstance(numeric["mean"], float)
    assert numeric["mean"] == (0.123456789 + 0.987654321) / 2
    assert "sample_rows" not in exported
    assert "head_rows" not in exported
    assert "tail_rows" not in exported
    assert "sample_values" not in json.dumps(exported)
    assert "sample-only-secret" not in json.dumps(exported)


def test_export_serializes_undefined_statistics_as_null_and_strict_json():
    uploaded_file = UploadedFile(filename="empty.csv", content=b"value\n", file_type="csv")
    profile = build_profile_model(
        uploaded_file=uploaded_file,
        dataframe=pl.DataFrame({"value": pl.Series([], dtype=pl.Float64)}),
        read_time_ms=0,
        warnings=[],
    )

    text = serialize_profile_json(
        profile,
        datasetpeek_version="0.5.0",
        generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )

    assert "NaN" not in text
    assert "Infinity" not in text
    json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def test_export_exposes_no_source_uri_or_credentials():
    profile = make_profile()
    text = serialize_profile_json(
        profile,
        datasetpeek_version="0.5.0",
        generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )

    assert "s3://" not in text
    assert "DATASETPEEK_S3_SECRET_ACCESS_KEY" not in text
