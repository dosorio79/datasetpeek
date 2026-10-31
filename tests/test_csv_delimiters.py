from __future__ import annotations

import pytest

from app.services.file_reader import FileValidationError, UploadedFile, read_uploaded_file


def _read_csv_bytes(filename: str, content: str):
    uploaded_file = UploadedFile(
        filename=filename,
        content=content.encode("utf-8"),
        file_type="csv",
    )
    return read_uploaded_file(uploaded_file)


def test_csv_auto_detects_semicolon_delimiter():
    dataframe, read_time_ms, warnings = _read_csv_bytes(
        "semicolon.csv",
        "name;score\nalice;10\nbob;20\n",
    )

    assert dataframe.columns == ["name", "score"]
    assert dataframe.to_dicts() == [{"name": "alice", "score": 10}, {"name": "bob", "score": 20}]
    assert read_time_ms >= 0
    assert warnings == []


def test_csv_auto_detects_tab_delimiter():
    dataframe, read_time_ms, warnings = _read_csv_bytes(
        "tab.csv",
        "name\tscore\nalice\t10\nbob\t20\n",
    )

    assert dataframe.columns == ["name", "score"]
    assert dataframe.to_dicts() == [{"name": "alice", "score": 10}, {"name": "bob", "score": 20}]
    assert read_time_ms >= 0
    assert warnings == []


def test_csv_rejects_unsupported_delimiter_instead_of_misprofiling():
    with pytest.raises(FileValidationError, match="supported CSV delimiter"):
        _read_csv_bytes(
            "pipe.csv",
            "name|score\nalice|10\nbob|20\n",
        )


def test_csv_without_detectable_delimiter_keeps_rows():
    frame, _, warnings = _read_csv_bytes("single.csv", "name\nalice\nbob\n")
    assert frame.to_dicts() == [{"name": "alice"}, {"name": "bob"}]
    assert any("could not be auto-detected" in warning for warning in warnings)


def test_csv_tolerant_fallback_preserves_mixed_values(monkeypatch):
    monkeypatch.setenv("DATASETPEEK_CSV_INFER_SCHEMA_ROWS", "1")
    frame, _, warnings = _read_csv_bytes("mixed.csv", "id,value\n1,10\n2,word\n")
    assert frame.to_dicts() == [{"id": "1", "value": "10"}, {"id": "2", "value": "word"}]
    assert any("inconsistent values" in warning for warning in warnings)


def test_non_comma_parse_failure_falls_back_without_losing_rows(monkeypatch):
    import app.services.file_reader as reader

    original = reader.pl.read_csv
    monkeypatch.setattr(reader, "_detect_csv_separator", lambda content: (";", True))

    def fail_detected_separator(*args, **kwargs):
        if kwargs.get("separator") == ";":
            raise ValueError("synthetic detected-separator failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(reader.pl, "read_csv", fail_detected_separator)
    frame, _, warnings = _read_csv_bytes("fallback.csv", "id,name\n1,alice\n2,bob\n")
    assert frame["name"].to_list() == ["alice", "bob"]
    assert [str(value) for value in frame["id"]] == ["1", "2"]
    assert any("falling back to comma" in warning for warning in warnings)
