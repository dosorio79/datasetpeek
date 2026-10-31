from types import SimpleNamespace

import pytest

from app.services import file_reader
from app.services.file_reader import FileValidationError, UploadedFile, read_uploaded_file


@pytest.mark.parametrize(
    ("filename", "content", "kind", "message"),
    [
        ("broken.parquet", b"not parquet", "parquet", "Could not parse broken.parquet"),
        ("empty.csv", b"id,name\n", "csv", "no rows to profile"),
    ],
)
def test_invalid_file_reports_validation_error(filename, content, kind, message):
    with pytest.raises(FileValidationError, match=message):
        read_uploaded_file(UploadedFile(filename, content, kind))


def test_parser_failure_is_wrapped(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic parser failure")

    monkeypatch.setattr(file_reader.pl, "read_parquet", fail)
    with pytest.raises(FileValidationError, match="Could not parse broken.parquet") as error:
        read_uploaded_file(UploadedFile("broken.parquet", b"PAR1", "parquet"))
    assert isinstance(error.value.__cause__, RuntimeError)


def multipart(*, name="dataset", filename="data.csv", payload=b"id\n1\n"):
    disposition = f'form-data; name="{name}"'
    if filename is not None:
        disposition += f'; filename="{filename}"'
    return (
        f"--boundary\r\nContent-Disposition: {disposition}\r\n\r\n".encode()
        + payload
        + b"\r\n--boundary--\r\n"
    )


@pytest.mark.parametrize(
    ("body", "content_type", "message"),
    [
        (multipart(), "multipart/form-data", "before analyzing"),
        (multipart(filename=None), "multipart/form-data; boundary=boundary", "before analyzing"),
        (multipart(name="other"), "multipart/form-data; boundary=boundary", "before analyzing"),
        (multipart(payload=b""), "multipart/form-data; boundary=boundary", "non-empty"),
        (multipart(filename="data.txt"), "multipart/form-data; boundary=boundary", "Unsupported"),
        (object(), "multipart/form-data; boundary=boundary", "before analyzing"),
    ],
)
def test_invalid_multipart_is_rejected(body, content_type, message):
    request = SimpleNamespace(body=body, headers={"content-type": content_type})
    with pytest.raises(FileValidationError, match=message):
        UploadedFile.from_request_files(files=None, request=request)


def test_bytearray_multipart_body_preserves_bytes():
    request = SimpleNamespace(
        body=bytearray(multipart()),
        headers={"content-type": "multipart/form-data; boundary=boundary"},
    )
    uploaded = UploadedFile.from_request_files(files=None, request=request)
    assert uploaded.filename == "data.csv"
    assert uploaded.content == b"id\n1\n"


@pytest.mark.parametrize("key", ["content", "body", "data"])
@pytest.mark.parametrize("as_bytearray", [False, True])
def test_upload_wrapper_preserves_bytes(key, as_bytearray):
    payload = b"id\n1\n"
    value = bytearray(payload) if as_bytearray else payload
    uploaded = UploadedFile.from_request_files(
        files={"dataset": {"filename": "data.csv", key: value}}
    )
    assert uploaded.content == payload
    assert isinstance(uploaded.content, bytes)


@pytest.mark.parametrize("attribute", ["content", "body"])
def test_attribute_upload_wrapper_preserves_bytearray_bytes(attribute):
    payload = b"id\n1\n"
    candidate = SimpleNamespace(filename="data.csv", **{attribute: bytearray(payload)})
    uploaded = UploadedFile.from_request_files(files={"dataset": candidate})
    assert uploaded.content == payload
    assert isinstance(uploaded.content, bytes)
