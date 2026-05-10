from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import polars as pl
from robyn.testing import TestClient as RobynClient

import app.routes.profile as profile_routes
import app.services.file_reader as file_reader
from main import parse_runtime_config
from app.main import create_app
from app.services.file_reader import FileValidationError, UploadedFile, read_uploaded_file
from app.services.heuristics import detect_column_signals
from app.services.profiler import build_profile_view_model

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_read_uploaded_csv_and_detect_signals():
    uploaded_file = UploadedFile(
        filename="sample_profile.csv",
        content=(FIXTURE_DIR / "sample_profile.csv").read_bytes(),
        file_type="csv",
    )

    dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)
    profile = build_profile_view_model(
        uploaded_file=uploaded_file,
        dataframe=dataframe,
        read_time_ms=read_time_ms,
        warnings=warnings,
        upload_token="token",
        sample_seed=42,
    )

    signal_kinds = {(signal["column"], signal["kind"]) for signal in profile["signals"]}
    assert ("customer_id", "Possible ID") in signal_kinds
    assert ("status", "Low variance") in signal_kinds
    assert ("churn_flag", "Binary / target") in signal_kinds
    assert ("mostly_missing", "Mostly missing") in signal_kinds
    assert ("mixed_value", "Suspicious mixed types") in signal_kinds
    assert ("mostly_missing", "Binary / target") not in signal_kinds
    assert ("mostly_missing", "Possible ID") not in signal_kinds
    assert ("status", "Binary / target") not in signal_kinds
    assert ("notes", "Possible ID") not in signal_kinds
    assert ("mixed_value", "Possible ID") not in signal_kinds
    assert ("score", "Possible ID") not in signal_kinds
    assert ("customer_id", "Likely categorical") not in signal_kinds
    assert ("opt_in_text", "Boolean disguised as string") in signal_kinds
    assert ("opt_in_text", "Binary / target") not in signal_kinds
    assert ("opt_in_text", "Likely categorical") not in signal_kinds
    assert ("churn_flag", "Likely categorical") not in signal_kinds
    assert profile["file_summary"]["rows"] == 12
    assert len(profile["sample_rows"]) == 10


def test_read_uploaded_parquet(tmp_path):
    dataframe = pl.read_csv(FIXTURE_DIR / "sample_profile.csv")
    parquet_path = tmp_path / "sample_profile.parquet"
    dataframe.write_parquet(parquet_path)

    uploaded_file = UploadedFile(
        filename="sample_profile.parquet",
        content=parquet_path.read_bytes(),
        file_type="parquet",
    )

    profiled_frame, read_time_ms, warnings = read_uploaded_file(uploaded_file)
    assert profiled_frame.shape == dataframe.shape
    assert read_time_ms >= 0
    assert warnings == []


def test_extracts_filename_from_multipart_request_when_files_are_raw_bytes():
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()
    boundary = "----DataPeekBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="dataset"; filename="sample_profile.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    request = SimpleNamespace(
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    uploaded_file = UploadedFile.from_request_files({"dataset": csv_bytes}, request=request)

    assert uploaded_file.filename == "sample_profile.csv"
    assert uploaded_file.file_type == "csv"
    assert uploaded_file.content == csv_bytes


def test_extracts_upload_from_multipart_request_when_files_are_missing():
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()
    boundary = "----DataPeekBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="dataset"; filename="sample_profile.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = SimpleNamespace(
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    uploaded_file = UploadedFile.from_request_files(None, request=request)

    assert uploaded_file.filename == "sample_profile.csv"
    assert uploaded_file.file_type == "csv"
    assert uploaded_file.content == csv_bytes


def test_multipart_extraction_selects_dataset_part_only():
    csv_bytes = b"id,name\n1,Alice\n"
    decoy_bytes = b"not,the,dataset\n"
    boundary = "----DataPeekBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="attachment"; filename="decoy.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + decoy_bytes + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="dataset"; filename="customers.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = SimpleNamespace(
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    uploaded_file = UploadedFile.from_request_files(None, request=request)

    assert uploaded_file.filename == "customers.csv"
    assert uploaded_file.content == csv_bytes


def test_extracts_filename_from_string_multipart_body():
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()
    boundary = "----DataPeekBoundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="dataset"; filename="original_name.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + csv_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    request = SimpleNamespace(
        body=body.decode("utf-8", errors="ignore"),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    uploaded_file = UploadedFile.from_request_files({"dataset": csv_bytes}, request=request)

    assert uploaded_file.filename == "original_name.csv"
    assert uploaded_file.file_type == "csv"


def test_rejects_oversized_upload(monkeypatch):
    monkeypatch.setattr(file_reader, "MAX_UPLOAD_BYTES", 10)

    try:
        UploadedFile.from_request_files({"dataset": b"id,name\n1,Alice\n"}, preferred_filename="customers.csv")
    except FileValidationError as exc:
        assert "currently supports files up to" in str(exc)
    else:
        raise AssertionError("Expected oversized upload to be rejected")


def test_infers_csv_type_when_filename_metadata_is_missing():
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()

    uploaded_file = UploadedFile.from_request_files({"dataset": csv_bytes})

    assert uploaded_file.filename == "upload.csv"
    assert uploaded_file.file_type == "csv"
    assert uploaded_file.content == csv_bytes


def test_prefers_filename_from_form_data_when_metadata_is_missing():
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()

    uploaded_file = UploadedFile.from_request_files(
        {"dataset": csv_bytes},
        preferred_filename="customers.csv",
    )

    assert uploaded_file.filename == "customers.csv"
    assert uploaded_file.file_type == "csv"


def test_reads_public_s3_uri_through_upload_model(monkeypatch):
    csv_bytes = b"zone_id,zone_name\n1,Newark Airport\n"
    calls = []

    def download_s3_object(*, bucket, key, max_bytes):
        calls.append((bucket, key))
        return csv_bytes

    monkeypatch.setattr(file_reader, "download_s3_object", download_s3_object)

    uploaded_file = UploadedFile.from_s3_uri("s3://nyc-tlc/misc/taxi_zone_lookup.csv")

    assert calls == [("nyc-tlc", "misc/taxi_zone_lookup.csv")]
    assert uploaded_file.filename == "s3://nyc-tlc/misc/taxi_zone_lookup.csv"
    assert uploaded_file.file_type == "csv"
    assert uploaded_file.content == csv_bytes


def test_rejects_unsupported_s3_object_type(monkeypatch):
    def fail_download(*, bucket, key, max_bytes):
        raise AssertionError("Unsupported extension should be rejected before download")

    monkeypatch.setattr(file_reader, "download_s3_object", fail_download)

    try:
        UploadedFile.from_s3_uri("s3://bucket/path/data.json")
    except FileValidationError as exc:
        assert "Unsupported S3 object type" in str(exc)
    else:
        raise AssertionError("Expected unsupported S3 object to be rejected")


def test_routes_render_profile_and_resample():
    client = RobynClient(create_app())
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()

    analyze_response = client.post(
        "/analyze",
        files={"dataset": {"filename": "sample_profile.csv", "content": csv_bytes}},
    )

    assert analyze_response.status_code == 200
    assert "<span>Rows</span>" in analyze_response.text
    assert "profiles the full uploaded file or S3 object" in analyze_response.text
    assert "Sample rows (random)" in analyze_response.text
    assert "Column Overview" in analyze_response.text
    assert "Signals / Warnings" in analyze_response.text
    assert "Boolean disguised as string" in analyze_response.text

    token = _extract_hidden_value(analyze_response.text, "upload_token")
    next_seed = _extract_hidden_value(analyze_response.text, "resample_seed")

    resample_response = client.post(
        "/resample",
        form_data={"upload_token": token, "resample_seed": next_seed},
    )

    assert resample_response.status_code == 200
    assert "Sample rows (random)" in resample_response.text


def test_route_analyzes_s3_uri(monkeypatch):
    client = RobynClient(create_app())
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()

    def download_s3_object(*, bucket, key, max_bytes):
        assert bucket == "nyc-tlc"
        assert key == "misc/taxi_zone_lookup.csv"
        return csv_bytes

    monkeypatch.setattr(file_reader, "download_s3_object", download_s3_object)

    response = client.post(
        "/analyze",
        form_data={"s3_uri": "s3://nyc-tlc/misc/taxi_zone_lookup.csv"},
    )

    assert response.status_code == 200
    assert "s3://nyc-tlc/misc/taxi_zone_lookup.csv" in response.text
    assert "Column Overview" in response.text


def test_home_renders_help_menu():
    client = RobynClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Analyze dataset" in response.text
    assert "Choose a local CSV/Parquet file or a configured S3-compatible object." in response.text
    assert 'name="source_mode" value="file" checked' in response.text
    assert 'name="source_mode" value="s3"' in response.text
    assert 'data-source-panel="file"' in response.text
    assert 'data-source-panel="s3"' in response.text
    assert "Local file" in response.text
    assert "S3 / MinIO URI" in response.text
    assert "Uses the server-configured object storage credentials." in response.text
    assert "row count" in response.text
    assert "S3-compatible URI" in response.text
    assert "DATAPEEK_S3_ENDPOINT_URL" in response.text
    assert 'id="analyze-submit"' in response.text


def test_resample_renders_validation_errors(monkeypatch):
    client = RobynClient(create_app())
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()
    analyze_response = client.post(
        "/analyze",
        files={"dataset": {"filename": "sample_profile.csv", "content": csv_bytes}},
    )
    token = _extract_hidden_value(analyze_response.text, "upload_token")

    def fail_read(*args, **kwargs):
        raise FileValidationError("Could not parse cached upload.")

    monkeypatch.setattr(profile_routes, "read_uploaded_file", fail_read)

    resample_response = client.post(
        "/resample",
        form_data={"upload_token": token, "resample_seed": "43"},
    )

    assert resample_response.status_code == 200
    assert "Could not parse cached upload." in resample_response.text


def test_health_endpoint_returns_ok():
    client = RobynClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.text == '{"status":"ok"}'


def test_openapi_route_preparation_accepts_registered_handlers():
    app = create_app()

    app._add_openapi_routes()


def test_runtime_config_prefers_environment_port_and_default_host():
    host, port = parse_runtime_config(environ={"PORT": "9090"})

    assert host == "0.0.0.0"
    assert port == 9090


def test_runtime_config_allows_cli_overrides():
    host, port = parse_runtime_config(
        argv=["--host", "127.0.0.1", "--port", "7001"],
        environ={"HOST": "0.0.0.0", "PORT": "9090"},
    )

    assert host == "127.0.0.1"
    assert port == 7001


def _extract_hidden_value(html: str, field_name: str) -> str:
    marker = f'name="{field_name}" value="'
    start = html.index(marker) + len(marker)
    end = html.index('"', start)
    return html[start:end]


def test_numeric_discrete_encoding_signal():
    series = pl.Series("rating", [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2])
    row_count = len(series)
    unique_count = series.n_unique()
    missing_count = series.null_count()

    signals = detect_column_signals(
        column_name="rating",
        series=series,
        row_count=row_count,
        unique_count=unique_count,
        missing_count=missing_count,
    )

    kinds = {s["kind"] for s in signals}
    assert "Possible numeric discrete" in kinds


def test_numeric_discrete_signal_not_emitted_for_binary():
    series = pl.Series("flag", [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    row_count = len(series)
    signals = detect_column_signals(
        column_name="flag",
        series=series,
        row_count=row_count,
        unique_count=series.n_unique(),
        missing_count=series.null_count(),
    )
    kinds = {s["kind"] for s in signals}
    assert "Possible numeric discrete" not in kinds


def test_numeric_discrete_signal_not_emitted_for_id_column():
    series = pl.Series("user_id", list(range(1, 21)))
    row_count = len(series)
    signals = detect_column_signals(
        column_name="user_id",
        series=series,
        row_count=row_count,
        unique_count=series.n_unique(),
        missing_count=series.null_count(),
    )
    kinds = {s["kind"] for s in signals}
    assert "Possible numeric discrete" not in kinds
