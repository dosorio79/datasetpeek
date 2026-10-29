from __future__ import annotations

import csv
from datetime import datetime
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from types import SimpleNamespace

import polars as pl
from robyn.testing import TestClient as RobynClient

import app.services.file_reader as file_reader
from main import parse_runtime_config
from app.main import create_app
from app.services.file_reader import FileValidationError, UploadedFile, read_uploaded_file
from app.services.heuristics import detect_column_signals
from app.services.profile_export import serialize_profile_json
from app.services.profiler import build_profile_model, build_profile_view_model

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
    )

    signal_kinds = {(signal["column"], signal["kind"]) for signal in profile["signals"]}
    assert ("customer_id", "Possible ID") in signal_kinds
    assert ("status", "Low variance") in signal_kinds
    assert ("churn_flag", "Binary / possible target") in signal_kinds
    assert ("mostly_missing", "Mostly missing") in signal_kinds
    assert ("mixed_value", "Suspicious mixed types") in signal_kinds
    assert ("mostly_missing", "Binary / possible target") not in signal_kinds
    assert ("mostly_missing", "Possible ID") not in signal_kinds
    assert ("status", "Binary / possible target") not in signal_kinds
    assert ("notes", "Possible ID") not in signal_kinds
    assert ("mixed_value", "Possible ID") not in signal_kinds
    assert ("score", "Possible ID") not in signal_kinds
    assert ("customer_id", "Likely categorical") not in signal_kinds
    assert ("opt_in_text", "Boolean disguised as string") in signal_kinds
    assert ("opt_in_text", "Binary / possible target") not in signal_kinds
    assert ("opt_in_text", "Likely categorical") not in signal_kinds
    assert ("churn_flag", "Likely categorical") not in signal_kinds
    assert profile["file_summary"]["rows"] == 12
    assert len(profile["sample_rows"]) == 10


def test_profile_uses_operational_display_settings(monkeypatch):
    monkeypatch.setenv("DATASETPEEK_RANDOM_SAMPLE_ROWS", "3")
    monkeypatch.setenv("DATASETPEEK_HEAD_TAIL_ROWS", "2")
    monkeypatch.setenv("DATASETPEEK_SAMPLE_VALUE_COUNT", "1")
    monkeypatch.setenv("DATASETPEEK_TEXT_TRUNCATE_CHARS", "8")
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
    )

    assert len(profile["sample_rows"]) == 3
    assert len(profile["head_rows"]) == 2
    assert len(profile["tail_rows"]) == 2
    assert all(len(column["sample_values"]) <= 1 for column in profile["columns"])
    assert any("…" in row["notes"] for row in profile["sample_rows"])


def test_profile_adds_roles_top_values_orientation_reports(monkeypatch):
    monkeypatch.setenv("DATASETPEEK_TOP_VALUES_LIMIT", "2")
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
    )

    columns = {column["name"]: column for column in profile["columns"]}
    assert columns["customer_id"]["role"] == "Identifier"
    assert columns["churn_flag"]["role"] == "Binary flag"
    assert columns["opt_in_text"]["role"] == "Boolean flag"
    assert columns["segment"]["role"] == "Category"
    assert len(columns["segment"]["top_values"]) == 2
    assert "Likely identifier columns: customer_id." in profile["orientation"]
    assert "Confirm binary flag meaning and balance; decide whether any flag is an outcome." in profile["next_checks"]
    assert "# DatasetPeek Profile Report" in profile["markdown_report"]
    assert "## Column Overview" in profile["markdown_report"]
    assert "<!doctype html>" in profile["html_report"]
    assert "<script" not in profile["html_report"]
    assert "Sample rows" not in profile["html_report"]


def test_sample_cycling_does_not_render_uploaded_values_with_inner_html():
    template_source = (Path(__file__).parents[1] / "app" / "templates" / "home.html").read_text(encoding="utf-8")

    assert "sampleTableHead.innerHTML" not in template_source
    assert "sampleTableBody.innerHTML" not in template_source
    assert "textContent = row[column] ?? \"\"" in template_source


def test_profile_retains_raw_numeric_metrics_and_existing_report_format():
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
    columns = {column.name: column for column in profile.columns}
    numeric = next(column for column in profile.numeric_columns if column.name == "measure")

    assert columns["measure"].non_null_ratio == 2 / 10
    assert columns["measure"].missing_ratio == 8 / 10
    assert columns["group"].top_values[0].ratio == 8 / 10
    assert numeric.mean == (0.123456789 + 0.987654321) / 2
    assert "20.0%" in profile.markdown_report
    assert "0.556" in profile.markdown_report


def test_structured_profile_is_report_source():
    uploaded_file = UploadedFile(
        filename="sample_profile.csv",
        content=(FIXTURE_DIR / "sample_profile.csv").read_bytes(),
        file_type="csv",
    )
    dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)

    profile = build_profile_model(
        uploaded_file=uploaded_file,
        dataframe=dataframe,
        read_time_ms=read_time_ms,
        warnings=warnings,
    )

    assert profile.file_summary.rows == 12
    assert any(column.role == "Identifier" for column in profile.columns)
    assert profile.markdown_report
    assert profile.html_report


def test_csv_inconsistency_warning_becomes_quality_signal():
    uploaded_file = UploadedFile(
        filename="customers.csv",
        content=b"id,name\n1,Alice\n",
        file_type="csv",
    )
    dataframe = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

    profile = build_profile_view_model(
        uploaded_file=uploaded_file,
        dataframe=dataframe,
        read_time_ms=1,
        warnings=[file_reader.CSV_INCONSISTENT_ROWS_WARNING],
    )

    assert ("Dataset", "CSV inconsistency") in {
        (signal["column"], signal["kind"])
        for signal in profile["signals"]
    }
    assert any("text parsing" in check for check in profile["next_checks"])


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


def test_read_uploaded_csv_uses_configured_schema_inference(monkeypatch):
    calls = []

    def fake_read_csv(source, **kwargs):
        calls.append(kwargs)
        return pl.DataFrame({"id": [1], "value": ["ok"]})

    monkeypatch.setenv("DATASETPEEK_CSV_INFER_SCHEMA_ROWS", "1234")
    monkeypatch.setattr(file_reader.pl, "read_csv", fake_read_csv)
    uploaded_file = UploadedFile(
        filename="customers.csv",
        content=b"id,value\n1,ok\n",
        file_type="csv",
    )

    dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)

    assert dataframe.shape == (1, 2)
    assert read_time_ms >= 0
    assert warnings == []
    assert calls[0]["infer_schema_length"] == 1234


def test_extracts_filename_from_multipart_request_when_files_are_raw_bytes():
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()
    boundary = "----DatasetPeekBoundary"
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
    boundary = "----DatasetPeekBoundary"
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
    boundary = "----DatasetPeekBoundary"
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
    boundary = "----DatasetPeekBoundary"
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
    monkeypatch.setenv("DATASETPEEK_MAX_UPLOAD_MB", "1")
    oversized_csv = b"id,name\n" + (b"1,Alice\n" * 150000)

    try:
        UploadedFile.from_request_files({"dataset": oversized_csv}, preferred_filename="customers.csv")
    except FileValidationError as exc:
        assert "currently supports files up to 1 MB" in str(exc)
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


def test_routes_render_profile_and_sample_sets():
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
    assert "Next sample" in analyze_response.text
    assert "Sample 1" in analyze_response.text
    assert "Column Overview" in analyze_response.text
    assert "Data quality signals" in analyze_response.text
    assert "Dataset readout" in analyze_response.text
    assert "Suggested checks" in analyze_response.text
    assert "Export Markdown" in analyze_response.text
    assert "Export HTML" in analyze_response.text
    assert "<th>Role</th>" in analyze_response.text
    assert "<th>Top values</th>" in analyze_response.text
    assert "Boolean disguised as string" in analyze_response.text


def test_routes_render_profile_json_download_and_privacy_disclosure():
    client = RobynClient(create_app())
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()

    response = client.post(
        "/analyze",
        files={"dataset": {"filename": "sample_profile.csv", "content": csv_bytes}},
    )

    assert response.status_code == 200
    assert 'id="download-json"' in response.text
    assert "Export JSON" in response.text
    assert "top-value" in response.text.lower()
    assert 'id="profile-json-data"' in response.text
    assert '"profile-model.json"' in response.text

    match = re.search(
        r'<script type="application/json" id="profile-json-data">(.*?)</script>',
        response.text,
        re.S,
    )
    assert match
    document = json.loads(json.loads(match.group(1)))
    assert document["schema_version"] == "1.0.0"
    assert set(document) == {
        "schema_version",
        "metadata",
        "file",
        "columns",
        "numeric_summary",
        "signals",
        "orientation",
        "next_checks",
    }
    assert "sample_rows" not in document
    assert "head_rows" not in document
    assert "tail_rows" not in document
    assert "sample_values" not in json.dumps(document)


class _ScriptDataCollector(HTMLParser):
    def __init__(self, target_id):
        super().__init__()
        self.target_id = target_id
        self.capturing = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == self.target_id:
            self.capturing = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.capturing = False

    def handle_data(self, data):
        if self.capturing:
            self.parts.append(data)


def profile_json_from_html(html):
    collector = _ScriptDataCollector("profile-json-data")
    collector.feed(html)
    return json.loads(json.loads("".join(collector.parts)))


def test_profile_json_payload_round_trips_adversarial_values():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["category", "note"])
    for _ in range(8):
        writer.writerow(["</script>", "alpha"])
    writer.writerow(['quote " and unicode ☃', "beta"])
    writer.writerow(["line\nbreak", "gamma"])
    csv_bytes = buffer.getvalue().encode("utf-8")

    client = RobynClient(create_app())
    response = client.post(
        "/analyze",
        files={"dataset": {"filename": "adversarial.csv", "content": csv_bytes}},
    )
    assert response.status_code == 200

    collector = _ScriptDataCollector("profile-json-data")
    collector.feed(response.text)
    payload = "".join(collector.parts)
    assert "</script>" not in payload
    document = json.loads(json.loads(payload))

    dataframe = pl.read_csv(io.BytesIO(csv_bytes))
    expected = json.loads(
        serialize_profile_json(
            build_profile_model(
                uploaded_file=UploadedFile(
                    filename="adversarial.csv",
                    content=csv_bytes,
                    file_type="csv",
                ),
                dataframe=dataframe,
                read_time_ms=0,
                warnings=[],
            ),
            datasetpeek_version=document["metadata"]["datasetpeek_version"],
            generated_at=datetime.fromisoformat(
                document["metadata"]["generated_at"].replace("Z", "+00:00")
            ),
        )
    )
    assert document["columns"] == expected["columns"]
    assert document["signals"] == expected["signals"]
    assert document["orientation"] == expected["orientation"]
    assert document["next_checks"] == expected["next_checks"]

    category = next(column for column in document["columns"] if column["name"] == "category")
    values = [top["value"] for top in category["top_values"]]
    assert "</script>" in values
    assert any("☃" in value for value in values)
    assert any("\n" in value for value in values)
    for key in ("sample_rows", "head_rows", "tail_rows", "sample_values", "sample_sets"):
        assert key not in document


def test_route_exports_s3_basename(monkeypatch):
    client = RobynClient(create_app())
    csv_bytes = (FIXTURE_DIR / "sample_profile.csv").read_bytes()

    def download_s3_object(*, bucket, key, max_bytes):
        assert bucket == "private-bucket"
        assert key == "private-prefix/customers.csv"
        return csv_bytes

    monkeypatch.setattr(file_reader, "download_s3_object", download_s3_object)

    response = client.post(
        "/analyze",
        form_data={"s3_uri": "s3://private-bucket/private-prefix/customers.csv"},
    )

    assert response.status_code == 200
    collector = _ScriptDataCollector("profile-json-data")
    collector.feed(response.text)
    payload = "".join(collector.parts)
    document = json.loads(json.loads(payload))
    assert document["file"]["filename"] == "customers.csv"
    assert "private-prefix" not in payload
    assert "s3://private-bucket" not in payload


def test_empty_upload_does_not_offer_json_download():
    client = RobynClient(create_app())

    response = client.post(
        "/analyze",
        files={"dataset": {"filename": "empty.csv", "content": b""}},
    )

    assert response.status_code == 200
    assert 'id="download-json"' not in response.text
    assert "empty" in response.text.lower()


def test_upload_first_and_error_states_do_not_offer_json_download():
    client = RobynClient(create_app())

    home = client.get("/")
    error = client.post("/analyze", files={"dataset": {"filename": "bad.txt", "content": b"bad"}})

    assert home.status_code == 200
    assert error.status_code == 200
    assert 'id="download-json"' not in home.text
    assert 'id="download-json"' not in error.text
    assert "Unsupported file type" in error.text


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


def test_readme_documents_profile_json_export_contract():
    repository_root = Path(__file__).parents[1]
    readme = (repository_root / "README.md").read_text(encoding="utf-8")
    prd = (repository_root / "docs" / "PRD.md").read_text(encoding="utf-8")

    assert "profile-model.json" in readme
    assert "schema_version" in readme
    assert "1.0.0" in readme
    assert "basename" in readme
    assert "top values" in readme.lower()
    assert "dataset content" in readme.lower()
    assert "superpowers/specs/2026-10-29-profile-model-json-design.md" in prd


def test_get_analyze_redirects_to_home():
    client = RobynClient(create_app())

    response = client.get("/analyze")

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


def test_home_renders_help_menu():
    client = RobynClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'meta property="og:title" content="DatasetPeek"' in response.text
    assert "https://raw.githubusercontent.com/dosorio79/datasetpeek/master/app/img/datasetpeek-logo.png" in response.text
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
    assert "DATASETPEEK_S3_ENDPOINT_URL" in response.text
    assert 'id="analyze-submit"' in response.text


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


def test_quality_signals_include_all_missing_constant_and_blank_strings():
    dataframe = pl.DataFrame(
        {
            "empty_col": [None, None, None],
            "constant_col": ["active", "active", "active"],
            "blank_col": ["", "value", "  "],
        }
    )

    signal_kinds = set()
    for series in dataframe.iter_columns():
        for signal in detect_column_signals(
            column_name=series.name,
            series=series,
            row_count=dataframe.height,
            unique_count=series.n_unique(),
            missing_count=series.null_count(),
        ):
            signal_kinds.add((signal["column"], signal["kind"]))

    assert ("empty_col", "All missing") in signal_kinds
    assert ("constant_col", "Constant value") in signal_kinds
    assert ("blank_col", "Blank strings") in signal_kinds
