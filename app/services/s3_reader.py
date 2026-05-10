from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from app.services.settings import get_settings


_S3_BUCKET_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


class S3ReadError(ValueError):
    """User-facing S3-compatible object read failure."""

    pass


@dataclass(frozen=True, slots=True)
class S3ClientConfig:
    endpoint_url: str | None
    region: str
    access_key_id: str | None
    secret_access_key: str | None
    session_token: str | None
    force_path_style: bool
    download_timeout_seconds: int

    @property
    def has_credentials(self) -> bool:
        return bool(self.access_key_id and self.secret_access_key)


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    parsed = urlparse((s3_uri or "").strip())
    if parsed.scheme.lower() != "s3":
        raise S3ReadError("Enter an S3 URI like s3://bucket/path/file.csv.")
    if not parsed.netloc or not parsed.path.strip("/"):
        raise S3ReadError("Enter an S3 URI like s3://bucket/path/file.csv.")
    if not _is_valid_s3_bucket_name(parsed.netloc):
        raise S3ReadError("Enter a valid S3 bucket name in the S3 URI.")
    return parsed.netloc, parsed.path.lstrip("/")


def download_s3_object(
    *,
    bucket: str,
    key: str,
    max_bytes: int,
    environ: Mapping[str, str] | None = None,
) -> bytes:
    config = s3_client_config_from_env(os.environ if environ is None else environ)
    urls = s3_object_urls(bucket=bucket, key=key, config=config)

    last_error: Exception | None = None
    for url in urls:
        try:
            content = read_s3_url(url=url, config=config, max_bytes=max_bytes)
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {400, 403, 404}:
                break
            continue
        except (OSError, URLError) as exc:
            last_error = exc
            continue

        if len(content) > max_bytes:
            raise S3ReadError(_oversized_message(max_bytes))
        return content

    raise S3ReadError(_download_error_message(error=last_error, config=config))


def s3_client_config_from_env(environ: Mapping[str, str]) -> S3ClientConfig:
    settings = get_settings(environ)
    endpoint_url = _first_env(environ, "DATAPEEK_S3_ENDPOINT_URL", "AWS_ENDPOINT_URL_S3", "AWS_S3_ENDPOINT_URL")
    access_key_id = _first_env(environ, "DATAPEEK_S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID")
    secret_access_key = _first_env(environ, "DATAPEEK_S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")
    session_token = _first_env(environ, "DATAPEEK_S3_SESSION_TOKEN", "AWS_SESSION_TOKEN")
    region = _first_env(environ, "DATAPEEK_S3_REGION", "AWS_REGION", "AWS_DEFAULT_REGION") or "us-east-1"
    force_path_style = _env_flag(environ, "DATAPEEK_S3_FORCE_PATH_STYLE", default=bool(endpoint_url))
    return S3ClientConfig(
        endpoint_url=_normalize_s3_endpoint_url(endpoint_url),
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
        force_path_style=force_path_style,
        download_timeout_seconds=settings.s3_download_timeout_seconds,
    )


def s3_object_urls(*, bucket: str, key: str, config: S3ClientConfig) -> tuple[str, ...]:
    quoted_key = quote(key, safe="/")
    if config.endpoint_url:
        return (f"{config.endpoint_url}/{bucket}/{quoted_key}",)

    path_style_url = f"https://s3.amazonaws.com/{bucket}/{quoted_key}"
    if config.force_path_style:
        return (path_style_url,)
    return (f"https://{bucket}.s3.amazonaws.com/{quoted_key}", path_style_url)


def read_s3_url(*, url: str, config: S3ClientConfig, max_bytes: int) -> bytes:
    headers = {"User-Agent": "DataPeek"}
    if config.has_credentials:
        headers.update(s3_sigv4_headers(url=url, config=config))

    request = Request(url, headers=headers)
    with urlopen(request, timeout=config.download_timeout_seconds) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise S3ReadError(_oversized_message(max_bytes))
        return response.read(max_bytes + 1)


def s3_sigv4_headers(*, url: str, config: S3ClientConfig) -> dict[str, str]:
    if not config.access_key_id or not config.secret_access_key:
        return {}

    parsed = urlparse(url)
    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_hash = "UNSIGNED-PAYLOAD"
    canonical_uri = quote(parsed.path or "/", safe="/-_.~%")
    canonical_query = parsed.query
    headers = {
        "host": parsed.netloc,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    if config.session_token:
        headers["x-amz-security-token"] = config.session_token

    signed_headers = ";".join(sorted(headers))
    canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in sorted(headers))
    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{datestamp}/{config.region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = _s3_sigv4_signing_key(config.secret_access_key, datestamp, config.region)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        "AWS4-HMAC-SHA256 "
        f"Credential={config.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    return headers


def _is_valid_s3_bucket_name(bucket: str) -> bool:
    return bool(_S3_BUCKET_NAME_PATTERN.fullmatch(bucket)) and ".." not in bucket


def _first_env(environ: Mapping[str, str], *keys: str) -> str | None:
    for key in keys:
        value = environ.get(key)
        if value:
            return value
    return None


def _env_flag(environ: Mapping[str, str], key: str, *, default: bool) -> bool:
    value = environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_s3_endpoint_url(endpoint_url: str | None) -> str | None:
    if not endpoint_url:
        return None
    parsed = urlparse(endpoint_url)
    if not parsed.scheme or not parsed.netloc:
        raise S3ReadError("DATAPEEK_S3_ENDPOINT_URL must include scheme and host, for example http://localhost:9000.")
    return endpoint_url.rstrip("/")


def _s3_sigv4_signing_key(secret_access_key: str, datestamp: str, region: str) -> bytes:
    date_key = hmac.new(f"AWS4{secret_access_key}".encode("utf-8"), datestamp.encode("utf-8"), hashlib.sha256).digest()
    region_key = hmac.new(date_key, region.encode("utf-8"), hashlib.sha256).digest()
    service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def _oversized_message(max_bytes: int) -> str:
    max_mb = max_bytes // (1024 * 1024)
    return f"Upload is too large. DataPeek currently supports files up to {max_mb} MB."


def _download_error_message(*, error: Exception | None, config: S3ClientConfig) -> str:
    if isinstance(error, HTTPError) and error.code == 403:
        if config.has_credentials:
            return "S3 access denied (HTTP 403). Check the bucket policy, credentials, region, and endpoint."
        return (
            "S3 access denied (HTTP 403). If this object should be public, check the bucket policy, public access "
            "settings, requester-pays status, bucket name, and object path. For private buckets, configure "
            "DATAPEEK_S3_ACCESS_KEY_ID and DATAPEEK_S3_SECRET_ACCESS_KEY; for MinIO/custom S3, also configure "
            "DATAPEEK_S3_ENDPOINT_URL."
        )
    if isinstance(error, HTTPError) and error.code == 404:
        return "S3 object not found (HTTP 404). Check the bucket name and object path."
    if isinstance(error, HTTPError):
        return f"Could not download S3 object. HTTP {error.code}."
    return "Could not download S3 object. Confirm the URI, endpoint, and credentials are correct."
