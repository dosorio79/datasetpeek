from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import app.services.s3_reader as s3_reader
from app.services.s3_reader import S3ReadError


def test_rejects_invalid_s3_uri():
    try:
        s3_reader.parse_s3_uri("https://example.com/data.csv")
    except S3ReadError as exc:
        assert "Enter an S3 URI" in str(exc)
    else:
        raise AssertionError("Expected invalid S3 URI to be rejected")


def test_rejects_invalid_s3_bucket_name():
    try:
        s3_reader.parse_s3_uri("s3://bad_bucket/path/data.csv")
    except S3ReadError as exc:
        assert "valid S3 bucket name" in str(exc)
    else:
        raise AssertionError("Expected invalid S3 bucket to be rejected")


def test_builds_minio_path_style_url_from_endpoint_config():
    config = s3_reader.s3_client_config_from_env(
        {
            "DATASETPEEK_S3_ENDPOINT_URL": "http://localhost:9000",
            "DATASETPEEK_S3_REGION": "us-east-1",
        }
    )

    assert s3_reader.s3_object_urls(bucket="datasets", key="folder/data.csv", config=config) == (
        "http://localhost:9000/datasets/folder/data.csv",
    )


def test_s3_config_uses_download_timeout_setting():
    config = s3_reader.s3_client_config_from_env({"DATASETPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS": "9"})

    assert config.download_timeout_seconds == 9


def test_builds_signed_s3_headers_from_credentials():
    config = s3_reader.s3_client_config_from_env(
        {
            "DATASETPEEK_S3_ACCESS_KEY_ID": "minioadmin",
            "DATASETPEEK_S3_SECRET_ACCESS_KEY": "minioadmin",
            "DATASETPEEK_S3_REGION": "us-east-1",
        }
    )

    headers = s3_reader.s3_sigv4_headers(url="http://localhost:9000/datasets/folder/data.csv", config=config)

    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=minioadmin/")
    assert headers["x-amz-content-sha256"] == "UNSIGNED-PAYLOAD"
    assert "x-amz-date" in headers


def test_downloads_from_minio_style_endpoint_with_signed_request():
    observed = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed["path"] = self.path
            observed["authorization"] = self.headers.get("Authorization")
            observed["content_hash"] = self.headers.get("x-amz-content-sha256")
            body = b"id,name\n1,Alice\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.handle_request)
    thread.start()

    try:
        content = s3_reader.download_s3_object(
            bucket="datasets",
            key="folder/data.csv",
            max_bytes=1024,
            environ={
                "DATASETPEEK_S3_ENDPOINT_URL": f"http://127.0.0.1:{server.server_port}",
                "DATASETPEEK_S3_ACCESS_KEY_ID": "minioadmin",
                "DATASETPEEK_S3_SECRET_ACCESS_KEY": "minioadmin",
                "DATASETPEEK_S3_REGION": "us-east-1",
            },
        )
    finally:
        server.server_close()
        thread.join(timeout=1)

    assert content == b"id,name\n1,Alice\n"
    assert observed["path"] == "/datasets/folder/data.csv"
    assert observed["authorization"].startswith("AWS4-HMAC-SHA256 Credential=minioadmin/")
    assert observed["content_hash"] == "UNSIGNED-PAYLOAD"


def test_anonymous_403_explains_public_and_private_access_options(monkeypatch):
    class Forbidden(s3_reader.HTTPError):
        def __init__(self):
            super().__init__("http://example.com/object.csv", 403, "Forbidden", hdrs=None, fp=None)

    def deny(*, url, config, max_bytes):
        raise Forbidden()

    monkeypatch.setattr(s3_reader, "read_s3_url", deny)

    try:
        s3_reader.download_s3_object(
            bucket="datasets",
            key="folder/data.csv",
            max_bytes=1024,
            environ={},
        )
    except S3ReadError as exc:
        message = str(exc)
        assert "S3 access denied (HTTP 403)" in message
        assert "If this object should be public" in message
        assert "bucket policy" in message
        assert "requester-pays" in message
        assert "DATASETPEEK_S3_ACCESS_KEY_ID" in message
        assert "DATASETPEEK_S3_ENDPOINT_URL" in message
    else:
        raise AssertionError("Expected anonymous 403 to explain credential configuration")


def test_accepts_legacy_datapeek_s3_env_names():
    config = s3_reader.s3_client_config_from_env({"DATAPEEK_S3_REGION": "eu-west-1"})

    assert config.region == "eu-west-1"
