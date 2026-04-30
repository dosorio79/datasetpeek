from __future__ import annotations

import csv
import re
from email.parser import BytesParser
from email.policy import default
from dataclasses import dataclass
from io import BytesIO
from time import perf_counter
from typing import Any

import polars as pl


_CSV_DELIMITER_CANDIDATES = (",", ";", "\t")
_FILENAME_PATTERN = re.compile(r'filename="([^"]+)"')


class FileValidationError(ValueError):
    """User-facing upload or parsing validation failure."""

    pass


@dataclass(slots=True)
class UploadedFile:
    """Normalized file upload accepted by the profiling pipeline."""

    filename: str
    content: bytes
    file_type: str

    @classmethod
    def from_request_files(
        cls,
        files: Any,
        request: Any | None = None,
        preferred_filename: str | None = None,
    ) -> "UploadedFile":
        """Normalize Robyn multipart inputs into a supported CSV or Parquet file."""

        candidate = _unwrap_uploaded_value(files)
        filename = preferred_filename or _read_attr(candidate, "filename") or _read_attr(candidate, "name") or "upload"
        content = _read_bytes(candidate)

        if filename == "upload" and request is not None:
            multipart_file = _extract_upload_from_multipart_request(request)
            if multipart_file is not None:
                return multipart_file

        if not content:
            raise FileValidationError("Upload a non-empty CSV or Parquet file.")

        lowered = filename.lower()
        if lowered.endswith(".csv"):
            file_type = "csv"
        elif lowered.endswith(".parquet"):
            file_type = "parquet"
        else:
            file_type = _infer_file_type(content)
            if file_type == "csv" and filename == "upload":
                filename = "upload.csv"
            elif file_type == "parquet" and filename == "upload":
                filename = "upload.parquet"
            else:
                raise FileValidationError("Unsupported file type. Upload a CSV or Parquet file.")

        return cls(filename=filename, content=content, file_type=file_type)


def read_uploaded_file(uploaded_file: UploadedFile) -> tuple[pl.DataFrame, int, list[str]]:
    """Read an uploaded file into Polars and return elapsed read time plus warnings."""

    start = perf_counter()
    warnings: list[str] = []

    try:
        if uploaded_file.file_type == "csv":
            dataframe = _read_csv(uploaded_file.content, warnings)
        else:
            dataframe = pl.read_parquet(BytesIO(uploaded_file.content))
    except Exception as exc:  # pragma: no cover - exact parser errors vary by dependency version
        raise FileValidationError(f"Could not parse {uploaded_file.filename}: {exc}") from exc

    if dataframe.height == 0:
        raise FileValidationError("The uploaded file has no rows to profile.")

    elapsed_ms = int((perf_counter() - start) * 1000)
    return dataframe, elapsed_ms, warnings


def _read_csv(content: bytes, warnings: list[str]) -> pl.DataFrame:
    """Read CSV content with delimiter detection and a conservative fallback path."""

    separator, auto_detected = _detect_csv_separator(content)
    if not auto_detected:
        warnings.append("CSV delimiter could not be auto-detected; falling back to comma.")

    try:
        dataframe = pl.read_csv(BytesIO(content), separator=separator)
    except Exception:
        if separator != ",":
            warnings.append(f"Detected CSV delimiter {separator!r} failed to parse cleanly; falling back to comma.")
            try:
                dataframe = pl.read_csv(BytesIO(content), separator=",")
            except Exception:
                pass

        warnings.append("CSV parsing fell back to a string-oriented read for inconsistent rows.")
        dataframe = pl.read_csv(BytesIO(content), separator=",", infer_schema=False, ignore_errors=True)

    if _looks_like_unsupported_delimiter_csv(content, dataframe, separator):
        raise FileValidationError("Could not detect a supported CSV delimiter. Use comma, semicolon, or tab.")

    return dataframe


def _detect_csv_separator(content: bytes) -> tuple[str, bool]:
    """Detect a small supported delimiter set without turning CSV ingest into EDA."""

    sample = content[:65536].decode("utf-8", errors="replace")
    if not sample.strip():
        return ",", False

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_CSV_DELIMITER_CANDIDATES))
        if dialect.delimiter in _CSV_DELIMITER_CANDIDATES:
            return dialect.delimiter, True
    except csv.Error:
        pass

    lines = [line for line in sample.splitlines() if line.strip()]
    if not lines:
        return ",", False

    best_separator = ","
    best_score = (0, 0, 0)
    for separator in _CSV_DELIMITER_CANDIDATES:
        counts = [line.count(separator) for line in lines[:20]]
        if not any(counts):
            continue

        score = (
            sum(1 for count in counts if count > 0),
            -len(set(counts)),
            sum(counts),
        )
        if score > best_score:
            best_score = score
            best_separator = separator

    if best_score == (0, 0, 0):
        return ",", False
    return best_separator, True


def _looks_like_unsupported_delimiter_csv(content: bytes, dataframe: pl.DataFrame, separator: str) -> bool:
    if separator != "," or dataframe.width != 1:
        return False

    sample = content[:8192].decode("utf-8", errors="replace")
    lines = [line for line in sample.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    unsupported_delimiters = ("|", ":")
    return any(all(delimiter in line for line in lines[:3]) for delimiter in unsupported_delimiters)


def _unwrap_uploaded_value(files: Any) -> Any:
    if not files:
        return None

    if isinstance(files, dict):
        candidate = files.get("dataset")
        if candidate is None and files:
            candidate = next(iter(files.values()))
    else:
        candidate = files

    if isinstance(candidate, list):
        if not candidate:
            raise FileValidationError("Upload a CSV or Parquet file before analyzing.")
        return candidate[0]

    return candidate


def _read_attr(candidate: Any, attribute: str) -> str | None:
    if hasattr(candidate, attribute):
        value = getattr(candidate, attribute)
        if isinstance(value, str):
            return value
    if isinstance(candidate, dict):
        value = candidate.get(attribute)
        if isinstance(value, str):
            return value
    return None


def _read_bytes(candidate: Any) -> bytes:
    if candidate is None:
        raise FileValidationError("Upload a CSV or Parquet file before analyzing.")
    if isinstance(candidate, bytes):
        return candidate
    if isinstance(candidate, bytearray):
        return bytes(candidate)
    if hasattr(candidate, "content"):
        content = getattr(candidate, "content")
        if isinstance(content, bytes):
            return content
        if isinstance(content, bytearray):
            return bytes(content)
    if hasattr(candidate, "body"):
        body = getattr(candidate, "body")
        if isinstance(body, bytes):
            return body
        if isinstance(body, bytearray):
            return bytes(body)
    if isinstance(candidate, dict):
        for key in ("content", "body", "data"):
            value = candidate.get(key)
            if isinstance(value, bytes):
                return value
            if isinstance(value, bytearray):
                return bytes(value)
    raise FileValidationError("Upload a CSV or Parquet file before analyzing.")


def _extract_upload_from_multipart_request(request: Any) -> UploadedFile | None:
    """Recover file metadata from raw multipart bodies when Robyn omits it."""

    raw_body = getattr(request, "body", b"")
    if isinstance(raw_body, str):
        body = raw_body.encode("utf-8", errors="ignore")
    elif isinstance(raw_body, bytearray):
        body = bytes(raw_body)
    else:
        body = raw_body

    if not isinstance(body, bytes) or not body:
        return None

    headers = getattr(request, "headers", {}) or {}
    content_type = _header_value(headers, "content-type")
    if not content_type or "multipart/form-data" not in content_type.lower():
        return None

    raw_filename = _extract_filename_from_body(body)
    if raw_filename is not None:
        file_type = _file_type_from_filename(raw_filename)
        if file_type is not None:
            return UploadedFile(filename=raw_filename, content=_extract_payload_from_multipart(body), file_type=file_type)

    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + bytes(body)
    )

    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "dataset":
            continue
        filename = part.get_filename()
        if not filename:
            continue

        payload = part.get_payload(decode=True) or b""
        lowered = filename.lower()
        if lowered.endswith(".csv"):
            file_type = "csv"
        elif lowered.endswith(".parquet"):
            file_type = "parquet"
        else:
            raise FileValidationError("Unsupported file type. Upload a CSV or Parquet file.")

        return UploadedFile(filename=filename, content=payload, file_type=file_type)

    return None


def _extract_filename_from_body(body: bytes) -> str | None:
    match = _FILENAME_PATTERN.search(body.decode("utf-8", errors="ignore"))
    if match is None:
        return None
    return match.group(1)


def _extract_payload_from_multipart(body: bytes) -> bytes:
    # Fall back to a very small multipart extraction routine for Robyn bodies
    # that do not round-trip cleanly through the email parser.
    header_break = b"\r\n\r\n"
    start = body.find(header_break)
    if start == -1:
        return body
    payload = body[start + len(header_break) :]
    end_marker = payload.rfind(b"\r\n--")
    if end_marker == -1:
        return payload
    return payload[:end_marker]


def _header_value(headers: Any, key: str) -> str | None:
    if hasattr(headers, "get"):
        value = headers.get(key) or headers.get(key.title()) or headers.get(key.upper())
        if isinstance(value, str):
            return value
    if isinstance(headers, dict):
        for header_key, value in headers.items():
            if isinstance(header_key, str) and header_key.lower() == key.lower() and isinstance(value, str):
                return value
    return None


def _infer_file_type(content: bytes) -> str | None:
    """Infer file type only when upload metadata is missing."""

    if content.startswith(b"PAR1"):
        return "parquet"

    sample = content[:65536]
    if not sample.strip():
        return None

    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return None

    try:
        separator, _ = _detect_csv_separator(content)
        dataframe = pl.read_csv(BytesIO(content), separator=separator, n_rows=5)
    except Exception:
        return None

    return "csv" if dataframe.width >= 1 else None


def _file_type_from_filename(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith(".parquet"):
        return "parquet"
    return None
