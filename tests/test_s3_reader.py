from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.error import HTTPError, URLError

import pytest

import app.services.s3_reader as s3_reader
from app.services.s3_reader import S3ReadError

ENDPOINT_ENV = {"DATASETPEEK_S3_ENDPOINT_URL": "https://s3.test.invalid"}
CREDENTIAL_ENV = {
    **ENDPOINT_ENV,
    "DATASETPEEK_S3_ACCESS_KEY_ID": "sentinel-access-key",
    "DATASETPEEK_S3_SECRET_ACCESS_KEY": "sentinel-secret-key",
}


class FakeResponse:
    """Minimal urlopen response that records bounded reads."""

    def __init__(self, body: bytes, *, content_length: int | None = None) -> None:
        self.body = body
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        self.read_calls: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_calls.append(size)
        return self.body if size < 0 else self.body[:size]

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


class FakeUrlopen:
    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, int | None]] = []

    def __call__(self, request, timeout=None):
        self.calls.append((request.full_url, timeout))
        return self.responses.pop(0)


def test_s3_length_limit_before_read(monkeypatch):
    response = FakeResponse(b"x" * 101, content_length=101)
    monkeypatch.setattr(s3_reader, "urlopen", FakeUrlopen(response))
    config = s3_reader.s3_client_config_from_env(ENDPOINT_ENV)

    with pytest.raises(S3ReadError, match="too large"):
        s3_reader.read_s3_url(
            url="https://s3.test.invalid/bucket/data.csv", config=config, max_bytes=100
        )

    assert response.read_calls == []


@pytest.mark.parametrize("content_length", [None, 10])
def test_s3_stream_limit_without_trusted_length(monkeypatch, content_length):
    response = FakeResponse(b"x" * 150, content_length=content_length)
    monkeypatch.setattr(s3_reader, "urlopen", FakeUrlopen(response))

    with pytest.raises(S3ReadError, match="too large"):
        s3_reader.download_s3_object(
            bucket="bucket", key="data.csv", max_bytes=100, environ=ENDPOINT_ENV
        )

    assert response.read_calls == [101]


def test_s3_accepts_exact_limit(monkeypatch):
    body = b"x" * 100
    response = FakeResponse(body, content_length=100)
    monkeypatch.setattr(s3_reader, "urlopen", FakeUrlopen(response))

    content = s3_reader.download_s3_object(
        bucket="bucket", key="data.csv", max_bytes=100, environ=ENDPOINT_ENV
    )

    assert content == body
    assert response.read_calls == [101]


def test_s3_passes_configured_timeout(monkeypatch):
    fake_urlopen = FakeUrlopen(FakeResponse(b"data", content_length=4))
    monkeypatch.setattr(s3_reader, "urlopen", fake_urlopen)
    config = s3_reader.s3_client_config_from_env(
        {**ENDPOINT_ENV, "DATASETPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS": "9"}
    )

    s3_reader.read_s3_url(
        url="https://s3.test.invalid/bucket/data.csv", config=config, max_bytes=100
    )

    assert fake_urlopen.calls == [("https://s3.test.invalid/bucket/data.csv", 9)]


def _sentinel_http_error(code: int) -> HTTPError:
    return HTTPError(
        "https://s3.amazonaws.com/sentinel-bucket/private.csv?X-Amz-Signature=sentinel-signature",
        code,
        "sentinel-error-text sentinel-token",
        hdrs=None,
        fp=None,
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (403, "S3 access denied (HTTP 403)"),
        (404, "S3 object not found (HTTP 404)"),
        (500, "Could not download S3 object. HTTP 500."),
    ],
)
def test_authenticated_http_errors_do_not_leak_transport_details(monkeypatch, code, expected):
    def fail(**kwargs):
        raise _sentinel_http_error(code)

    monkeypatch.setattr(s3_reader, "read_s3_url", fail)

    with pytest.raises(S3ReadError) as error:
        s3_reader.download_s3_object(
            bucket="bucket", key="data.csv", max_bytes=100, environ=CREDENTIAL_ENV
        )

    message = str(error.value)
    assert expected in message
    for sentinel in (
        "sentinel-bucket",
        "sentinel-signature",
        "sentinel-token",
        "sentinel-error",
        "sentinel-access-key",
        "sentinel-secret-key",
        "s3.test.invalid",
    ):
        assert sentinel not in message
    if code == 403:
        assert "If this object should be public" not in message


@pytest.mark.parametrize(
    "transport_error", [TimeoutError("timed out"), URLError("sentinel-reason")]
)
def test_s3_transport_exhaustion_returns_stable_error(monkeypatch, transport_error):
    def fail(**kwargs):
        raise transport_error

    monkeypatch.setattr(s3_reader, "read_s3_url", fail)

    with pytest.raises(S3ReadError) as error:
        s3_reader.download_s3_object(bucket="bucket", key="data.csv", max_bytes=100, environ={})

    assert "Could not download S3 object." in str(error.value)
    assert "sentinel-reason" not in str(error.value)


def test_s3_alternate_url_success(monkeypatch):
    urls = []

    def read(*, url, config, max_bytes):
        urls.append(url)
        if len(urls) == 1:
            raise _sentinel_http_error(404)
        return b"id,name\n1,Alice\n"

    monkeypatch.setattr(s3_reader, "read_s3_url", read)

    content = s3_reader.download_s3_object(
        bucket="datasets", key="folder/data.csv", max_bytes=100, environ={}
    )

    assert content == b"id,name\n1,Alice\n"
    assert urls == [
        "https://datasets.s3.amazonaws.com/folder/data.csv",
        "https://s3.amazonaws.com/datasets/folder/data.csv",
    ]


def test_s3_retryable_exhaustion_is_bounded(monkeypatch):
    urls = []

    def read(*, url, config, max_bytes):
        urls.append(url)
        raise _sentinel_http_error(404)

    monkeypatch.setattr(s3_reader, "read_s3_url", read)

    with pytest.raises(S3ReadError, match="S3 object not found"):
        s3_reader.download_s3_object(
            bucket="datasets", key="folder/data.csv", max_bytes=100, environ={}
        )

    assert len(urls) == 2


@pytest.mark.parametrize("code", [500, 503])
def test_s3_nonretryable_error_does_not_retry(monkeypatch, code):
    urls = []

    def read(*, url, config, max_bytes):
        urls.append(url)
        raise _sentinel_http_error(code)

    monkeypatch.setattr(s3_reader, "read_s3_url", read)

    with pytest.raises(S3ReadError, match=f"HTTP {code}"):
        s3_reader.download_s3_object(
            bucket="datasets", key="folder/data.csv", max_bytes=100, environ={}
        )

    assert len(urls) == 1


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

    headers = s3_reader.s3_sigv4_headers(
        url="http://localhost:9000/datasets/folder/data.csv", config=config
    )

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
