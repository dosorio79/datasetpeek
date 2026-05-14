from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

BYTES_PER_MB = 1024 * 1024


class SettingsError(ValueError):
    """Invalid DatasetPeek runtime configuration."""

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
        max_upload_mb=_env_positive_int(env, "DATASETPEEK_MAX_UPLOAD_MB", "DATAPEEK_MAX_UPLOAD_MB", default=100),
        large_file_warning_mb=_env_positive_int(
            env,
            "DATASETPEEK_LARGE_FILE_WARNING_MB",
            "DATAPEEK_LARGE_FILE_WARNING_MB",
            default=50,
        ),
        random_sample_rows=_env_positive_int(
            env,
            "DATASETPEEK_RANDOM_SAMPLE_ROWS",
            "DATAPEEK_RANDOM_SAMPLE_ROWS",
            default=10,
        ),
        head_tail_rows=_env_positive_int(env, "DATASETPEEK_HEAD_TAIL_ROWS", "DATAPEEK_HEAD_TAIL_ROWS", default=5),
        sample_value_count=_env_positive_int(
            env,
            "DATASETPEEK_SAMPLE_VALUE_COUNT",
            "DATAPEEK_SAMPLE_VALUE_COUNT",
            default=3,
        ),
        text_truncate_chars=_env_positive_int(
            env,
            "DATASETPEEK_TEXT_TRUNCATE_CHARS",
            "DATAPEEK_TEXT_TRUNCATE_CHARS",
            default=50,
        ),
        top_values_limit=_env_positive_int(env, "DATASETPEEK_TOP_VALUES_LIMIT", "DATAPEEK_TOP_VALUES_LIMIT", default=5),
        s3_download_timeout_seconds=_env_positive_int(
            env,
            "DATASETPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS",
            "DATAPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS",
            default=30,
        ),
    )


def _env_positive_int(environ: Mapping[str, str], *keys: str, default: int) -> int:
    key, raw_value = _first_env_value(environ, *keys)
    if key is None or raw_value is None or raw_value.strip() == "":
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise SettingsError(f"{key} must be a positive integer.") from exc
    if value < 1:
        raise SettingsError(f"{key} must be a positive integer.")
    return value


def _first_env_value(environ: Mapping[str, str], *keys: str) -> tuple[str | None, str | None]:
    for key in keys:
        value = environ.get(key)
        if value is not None:
            return key, value
    return None, None
