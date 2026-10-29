from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import polars as pl
import pytest

from app.services.file_reader import UploadedFile, read_uploaded_file
from app.services.profile_export import serialize_profile_json
from app.services.profiler import build_profile_model


def make_profile(filename="metrics.csv"):
    uploaded_file = UploadedFile(
        filename=filename,
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
    assert set(exported) == {
        "schema_version",
        "metadata",
        "file",
        "columns",
        "numeric_summary",
        "signals",
        "orientation",
        "next_checks",
    }
    assert set(exported["metadata"]) == {"datasetpeek_version", "generated_at"}
    assert exported["metadata"] == {
        "datasetpeek_version": "0.5.0",
        "generated_at": "2026-10-29T12:00:00Z",
    }
    assert set(exported["file"]) == {
        "filename",
        "file_type",
        "rows",
        "columns",
        "read_time_ms",
    }
    assert [column["name"] for column in exported["columns"]] == ["measure", "group"]
    assert set(exported["columns"][0]) == {
        "name",
        "dtype",
        "role",
        "non_null_ratio",
        "missing_ratio",
        "unique_count",
        "top_values",
    }
    measure = next(column for column in exported["columns"] if column["name"] == "measure")
    assert measure["non_null_ratio"] == 2 / 10
    assert measure["missing_ratio"] == 8 / 10
    group = next(column for column in exported["columns"] if column["name"] == "group")
    assert len(group["top_values"]) == 1
    assert set(group["top_values"][0]) == {"value", "count", "ratio"}
    assert isinstance(group["top_values"][0]["count"], int)
    assert isinstance(group["top_values"][0]["ratio"], float)
    assert set(exported["numeric_summary"][0]) == {"name", "min", "max", "mean", "median"}
    numeric = exported["numeric_summary"][0]
    assert isinstance(numeric["mean"], float)
    assert numeric["mean"] == (0.123456789 + 0.987654321) / 2
    assert set(exported["signals"][0]) == {"column", "kind", "message"}
    assert "sample_rows" not in exported
    assert "head_rows" not in exported
    assert "tail_rows" not in exported
    assert "sample_values" not in json.dumps(exported)
    assert "sample_sets" not in json.dumps(exported)
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
    exported = json.loads(
        text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token))
    )

    assert exported["numeric_summary"] == [
        {"name": "value", "min": None, "max": None, "mean": None, "median": None}
    ]
    assert exported["columns"][0]["non_null_ratio"] == 0.0
    assert exported["columns"][0]["missing_ratio"] == 0.0


def test_top_value_ratio_uses_non_null_count():
    dataframe = pl.DataFrame(
        {"group": ["a", None, "a", "b", "b", None, "b", "a", None, "b"]}
    )
    profile = build_profile_model(
        uploaded_file=UploadedFile(filename="nullable.csv", content=b"", file_type="csv"),
        dataframe=dataframe,
        read_time_ms=2,
        warnings=[],
    )

    exported = json.loads(
        serialize_profile_json(
            profile,
            datasetpeek_version="0.5.0",
            generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
        )
    )
    group = exported["columns"][0]
    top_b = next(top for top in group["top_values"] if top["value"] == "b")

    assert top_b["count"] == 4
    assert top_b["ratio"] == 4 / 7


def test_export_keeps_integer_extrema_as_integers():
    dataframe = pl.DataFrame({"count": [1, 2, 3, 4]})
    profile = build_profile_model(
        uploaded_file=UploadedFile(filename="ints.csv", content=b"", file_type="csv"),
        dataframe=dataframe,
        read_time_ms=2,
        warnings=[],
    )

    exported = json.loads(
        serialize_profile_json(
            profile,
            datasetpeek_version="0.5.0",
            generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
        )
    )
    numeric = exported["numeric_summary"][0]

    assert numeric["min"] == 1
    assert numeric["max"] == 4
    assert isinstance(numeric["min"], int)
    assert isinstance(numeric["max"], int)
    assert numeric["mean"] == 2.5


def test_export_converts_decimal_parquet_statistics_to_json_numbers(tmp_path):
    parquet_path = tmp_path / "amounts.parquet"
    pl.DataFrame(
        {
            "amount": pl.Series(
                [Decimal("1.10"), Decimal("2.20")],
                dtype=pl.Decimal(precision=10, scale=2),
            )
        }
    ).write_parquet(parquet_path)
    uploaded_file = UploadedFile(
        filename="amounts.parquet",
        content=parquet_path.read_bytes(),
        file_type="parquet",
    )
    dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)
    profile = build_profile_model(
        uploaded_file=uploaded_file,
        dataframe=dataframe,
        read_time_ms=read_time_ms,
        warnings=warnings,
    )

    exported = json.loads(
        serialize_profile_json(
            profile,
            datasetpeek_version="0.5.0",
            generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
        )
    )

    numeric = exported["numeric_summary"][0]
    assert numeric["min"] == 1.1
    assert numeric["max"] == 2.2
    assert numeric["mean"] == 1.65
    assert numeric["median"] == 1.65
    assert "1.10" in profile.markdown_report


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_export_normalizes_non_finite_statistics(value):
    profile = make_profile()
    stats = replace(
        profile.numeric_columns[0],
        min=value,
        max=value,
        mean=value,
        median=value,
    )
    profile = replace(profile, numeric_columns=[stats])

    text = serialize_profile_json(
        profile,
        datasetpeek_version="0.5.0",
        generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    exported = json.loads(
        text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token))
    )

    assert exported["numeric_summary"][0] == {
        "name": stats.name,
        "min": None,
        "max": None,
        "mean": None,
        "median": None,
    }


def test_export_preserves_non_finite_display_in_reports():
    dataframe = pl.DataFrame({"x": [float("nan"), 1.0]})
    profile = build_profile_model(
        uploaded_file=UploadedFile(filename="finite.csv", content=b"", file_type="csv"),
        dataframe=dataframe,
        read_time_ms=2,
        warnings=[],
    )

    assert "nan" in profile.markdown_report.lower()
    assert "nan" in profile.html_report.lower()


@pytest.mark.parametrize(
    "source",
    [
        "s3://private-bucket/private-prefix/metrics.csv",
        "/private/uploads/metrics.csv",
        r"C:\private\uploads\metrics.csv",
    ],
)
def test_export_exposes_only_source_basename(source):
    profile = make_profile(filename=source)

    text = serialize_profile_json(
        profile,
        datasetpeek_version="0.5.0",
        generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    exported = json.loads(text)

    assert exported["file"]["filename"] == "metrics.csv"
    assert exported["orientation"][0].startswith("metrics.csv is a CSV dataset")
    assert "private" not in text
    assert "s3://" not in text


def test_export_retains_literal_nan_top_value():
    dataframe = pl.DataFrame({"group": ["NaN"] * 8 + ["other"] * 2})
    profile = build_profile_model(
        uploaded_file=UploadedFile(filename="nan.csv", content=b"", file_type="csv"),
        dataframe=dataframe,
        read_time_ms=2,
        warnings=[],
    )

    text = serialize_profile_json(
        profile,
        datasetpeek_version="0.5.0",
        generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
    )
    exported = json.loads(
        text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token))
    )

    group = next(column for column in exported["columns"] if column["name"] == "group")
    assert any(top["value"] == "NaN" for top in group["top_values"])


def test_export_normalizes_aware_timestamp_to_utc():
    timestamp = datetime(
        2026,
        10,
        29,
        12,
        0,
        tzinfo=timezone(timedelta(hours=2)),
    )

    exported = json.loads(
        serialize_profile_json(
            make_profile(),
            datasetpeek_version="0.5.0",
            generated_at=timestamp,
        )
    )

    assert exported["metadata"]["generated_at"] == "2026-10-29T10:00:00Z"


def test_export_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        serialize_profile_json(
            make_profile(),
            datasetpeek_version="0.5.0",
            generated_at=datetime(2026, 10, 29, 12, 0),
        )


def test_export_default_timestamp_is_utc_now():
    before = datetime.now(timezone.utc).replace(microsecond=0)
    text = serialize_profile_json(make_profile(), datasetpeek_version="0.5.0")
    after = datetime.now(timezone.utc) + timedelta(seconds=1)

    stamp = datetime.fromisoformat(
        json.loads(text)["metadata"]["generated_at"].replace("Z", "+00:00")
    )

    assert before <= stamp <= after
