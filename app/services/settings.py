from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

BYTES_PER_MB = 1024 * 1024


class SettingsError(ValueError):
    """Invalid DataPeek runtime configuration."""

    pass


@dataclass(frozen=True, slots=True)
class AppSettings:
    max_upload_mb: int = 100
    large_file_warning_mb: int = 50
    random_sample_rows: int = 10
    head_tail_rows: int = 5
    sample_value_count: int = 3
    text_truncate_chars: int = 50
    top_values_limit: int = 5
    s3_download_timeout_seconds: int = 30

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * BYTES_PER_MB

    @property
    def large_file_warning_bytes(self) -> int:
        return self.large_file_warning_mb * BYTES_PER_MB


def get_settings(environ: Mapping[str, str] | None = None) -> AppSettings:
    """Build runtime settings from environment variables.

    Settings are intentionally loaded on demand so tests, local runs, and
    managed deployments can change env vars without relying on module reloads.
    """

    env = os.environ if environ is None else environ
    return AppSettings(
        max_upload_mb=_env_positive_int(env, "DATAPEEK_MAX_UPLOAD_MB", 100),
        large_file_warning_mb=_env_positive_int(env, "DATAPEEK_LARGE_FILE_WARNING_MB", 50),
        random_sample_rows=_env_positive_int(env, "DATAPEEK_RANDOM_SAMPLE_ROWS", 10),
        head_tail_rows=_env_positive_int(env, "DATAPEEK_HEAD_TAIL_ROWS", 5),
        sample_value_count=_env_positive_int(env, "DATAPEEK_SAMPLE_VALUE_COUNT", 3),
        text_truncate_chars=_env_positive_int(env, "DATAPEEK_TEXT_TRUNCATE_CHARS", 50),
        top_values_limit=_env_positive_int(env, "DATAPEEK_TOP_VALUES_LIMIT", 5),
        s3_download_timeout_seconds=_env_positive_int(env, "DATAPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS", 30),
    )


def _env_positive_int(environ: Mapping[str, str], key: str, default: int) -> int:
    raw_value = environ.get(key)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise SettingsError(f"{key} must be a positive integer.") from exc
    if value < 1:
        raise SettingsError(f"{key} must be a positive integer.")
    return value
