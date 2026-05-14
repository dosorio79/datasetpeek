from __future__ import annotations

import pytest

from app.services.settings import BYTES_PER_MB, SettingsError, get_settings


def test_settings_defaults_match_current_runtime_behavior():
    settings = get_settings({})

    assert settings.max_upload_mb == 100
    assert settings.max_upload_bytes == 100 * BYTES_PER_MB
    assert settings.large_file_warning_mb == 50
    assert settings.large_file_warning_bytes == 50 * BYTES_PER_MB
    assert settings.random_sample_rows == 10
    assert settings.head_tail_rows == 5
    assert settings.sample_value_count == 3
    assert settings.text_truncate_chars == 50
    assert settings.top_values_limit == 5
    assert settings.s3_download_timeout_seconds == 30


def test_settings_read_operational_overrides_from_env():
    settings = get_settings(
        {
            "DATASETPEEK_MAX_UPLOAD_MB": "2",
            "DATASETPEEK_LARGE_FILE_WARNING_MB": "1",
            "DATASETPEEK_RANDOM_SAMPLE_ROWS": "4",
            "DATASETPEEK_HEAD_TAIL_ROWS": "2",
            "DATASETPEEK_SAMPLE_VALUE_COUNT": "1",
            "DATASETPEEK_TEXT_TRUNCATE_CHARS": "12",
            "DATASETPEEK_TOP_VALUES_LIMIT": "3",
            "DATASETPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS": "7",
        }
    )

    assert settings.max_upload_bytes == 2 * BYTES_PER_MB
    assert settings.large_file_warning_bytes == BYTES_PER_MB
    assert settings.random_sample_rows == 4
    assert settings.head_tail_rows == 2
    assert settings.sample_value_count == 1
    assert settings.text_truncate_chars == 12
    assert settings.top_values_limit == 3
    assert settings.s3_download_timeout_seconds == 7


def test_settings_accept_legacy_datapeek_env_names():
    settings = get_settings({"DATAPEEK_MAX_UPLOAD_MB": "2"})

    assert settings.max_upload_mb == 2


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_settings_reject_invalid_positive_integer(value):
    with pytest.raises(SettingsError, match="DATASETPEEK_MAX_UPLOAD_MB"):
        get_settings({"DATASETPEEK_MAX_UPLOAD_MB": value})
