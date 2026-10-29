# Profile Model JSON Implementation Plan

**Goal:** Add a downloadable, versioned JSON representation of a DatasetPeek profile without exporting preview rows.
**Architecture:** Retain raw numeric metrics in the structured profile while preserving existing display formatting. Add a dedicated serializer that maps `DatasetProfile` to the public schema, then pass its JSON string to the existing results-page client-side download pattern.
**Tech Stack:** Python 3.12, Robyn, Polars, Jinja2, pytest, browser-native JavaScript.
**Spec:** `docs/superpowers/specs/2026-10-29-profile-model-json-design.md`

**Status:** Revised for review; implementation is not authorized by this document.

## Global Constraints

- Do not serialize the dataclass, template context, or view model directly.
- Do not include raw preview/sample rows, head/tail rows, or per-column sample values.
- Include capped top-value strings; they may contain sensitive dataset content, so disclose this near the export action.
- Do not include credentials, S3 endpoint URLs, object URIs, local paths, or internal view-model/template fields.
- Do not add an API route, profile storage/history, JSON import, or schema comparison.
- Keep existing upload size limits and in-memory processing model.
- Preserve existing uncommitted work. Do not commit, push, or create branches unless explicitly requested.
- Keep DatasetPeek minimal; use the narrowest change and preserve existing Markdown/HTML output behavior.

## File Structure

- Modify `app/services/profile_model.py`: retain numeric ratios and numeric summary values alongside the display fields already consumed by reports.
- Modify `app/services/profiler.py`: populate raw metrics, preserve report formatting, and expose export JSON in the result view model.
- Create `app/services/profile_export.py`: own the explicit public JSON mapping and serialization.
- Modify `app/templates/home.html`: add the export control, privacy disclosure, JSON payload, and client-side download handler.
- Modify `tests/test_app.py`: cover numeric precision/report compatibility and rendered result/empty-state controls.
- Create `tests/test_profile_export.py`: cover schema, JSON types, omission/privacy boundaries, timestamp/version, and strict JSON behavior.
- Modify `README.md` and `docs/PRD.md`: document the shipped export after implementation; update release/version wording only when the release version is actually set.

## Review Focus

- Dataset values containing `</script>`, quotes, Unicode, or newlines must remain safely embedded and downloaded as data.
- Missing, empty, NaN, or infinite numeric statistics must not produce invalid JSON tokens.
- Percentage display strings must not be parsed back into rounded values; export ratios from raw calculations.
- Export must omit preview values while intentionally retaining capped top-value strings.
- Existing reports, error states, S3 profiles, and configured caps must remain unchanged.

### Task 1: Preserve Numeric Metrics Without Changing Report Presentation

**Files:**
- Modify: `app/services/profile_model.py`
- Modify: `app/services/profiler.py`
- Test: `tests/test_app.py`

**Interfaces:**
- `ColumnProfile` retains existing `non_null_pct` and `missing_pct` display strings and adds `non_null_ratio: float` and `missing_ratio: float`.
- `TopValue` retains existing `pct` display text and adds `ratio: float`, calculated as count divided by the non-null row count. Preserve the existing formatted/truncated `value` string; this export does not introduce raw top-value storage.
- Column ratios use total row count; both are `0.0` for an empty frame, matching existing display behavior.
- Keep integer extrema as integers. Convert Decimal statistics from numeric Parquet columns explicitly to JSON-compatible numbers, documenting possible float precision loss; map non-finite statistics to `None`.
- `NumericColumnSummary` stores `min`, `max`, `mean`, and `median` as `int | float | None`; report renderers format these values only at presentation time.

- [ ] **Step 1: Write the failing test** — add this test to `tests/test_app.py`:

  ```python
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
  ```

- [ ] Add focused cases for a nullable category (top-value ratio uses non-null count), an empty typed frame, integer extrema, and Decimal Parquet metrics. Assert existing Markdown/HTML and view-model formatting remains unchanged, including undefined/non-finite presentation.

- [ ] **Step 2: Run it and verify it fails** — `uv run pytest tests/test_app.py::test_profile_retains_raw_numeric_metrics_and_existing_report_format -q`; expect failure because the model currently stores formatted strings and top-value percentages only.
- [ ] **Step 3: Implement the minimal change** — add raw ratio fields to `ColumnProfile` and `TopValue`; retain current formatted fields for the existing reports. Change numeric summary values to raw numeric values or `None`, normalize non-finite values for export without silently changing existing non-finite report presentation (retain display fields if needed), and format numbers with the existing three-decimal display convention when generating Markdown/HTML and the view model. Populate these fields directly from Polars metrics; do not parse display strings.
- [ ] **Step 4: Run focused verification** — `uv run pytest tests/test_app.py -q`; expect all existing profiler/report tests and the new precision test to pass.

### Task 2: Add the Versioned JSON Serializer

**Files:**
- Create: `app/services/profile_export.py`
- Create: `tests/test_profile_export.py`

**Interfaces:**
- `serialize_profile_json(profile: DatasetProfile, *, datasetpeek_version: str, generated_at: datetime | None = None) -> str` returns compact UTF-8-compatible JSON text. If `generated_at` is omitted, use the current UTC time; normalize an aware supplied datetime to UTC; reject naive datetimes with `ValueError` rather than depending on the host timezone.
- The serializer emits the exact documented schema and uses `json.dumps(..., ensure_ascii=False, allow_nan=False)`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_profile_export.py` with a representative profile built through the public profiler API:

  ```python
  from dataclasses import replace
  from datetime import datetime, timezone
  import json
  import pytest

  import polars as pl

  from app.services.file_reader import UploadedFile
  from app.services.profile_export import serialize_profile_json
  from app.services.profiler import build_profile_model


  def make_profile():
      uploaded_file = UploadedFile(
          filename="metrics.csv",
          content=b"measure,group\n0.123456789,a\n0.987654321,a\n,b\n",
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
      return replace(
          profile,
          sample_rows=[{"measure": "sample-only-secret"}],
          head_rows=[{"measure": "sample-only-secret"}],
          tail_rows=[{"measure": "sample-only-secret"}],
          columns=[
              replace(column, sample_values=["sample-only-secret"])
              for column in profile.columns
          ],
      )


  def test_export_json_has_versioned_numeric_schema_and_excludes_previews(monkeypatch):
      monkeypatch.setenv("DATASETPEEK_TOP_VALUES_LIMIT", "1")
      profile = make_profile()
      timestamp = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)

      exported = json.loads(
          serialize_profile_json(profile, datasetpeek_version="0.5.0", generated_at=timestamp)
      )

      assert exported["schema_version"] == "1.0.0"
      assert exported["metadata"] == {
          "datasetpeek_version": "0.5.0",
          "generated_at": "2026-10-29T12:00:00Z",
      }
      assert [column["name"] for column in exported["columns"]] == ["measure", "group"]
      measure = next(column for column in exported["columns"] if column["name"] == "measure")
      assert measure["non_null_ratio"] == 2 / 10
      assert measure["missing_ratio"] == 8 / 10
      group = next(column for column in exported["columns"] if column["name"] == "group")
      assert len(group["top_values"]) == 1
      assert isinstance(group["top_values"][0]["count"], int)
      assert isinstance(group["top_values"][0]["ratio"], float)
      numeric = exported["numeric_summary"][0]
      assert isinstance(numeric["mean"], float)
      assert numeric["mean"] == (0.123456789 + 0.987654321) / 2
      assert "sample_rows" not in exported
      assert "head_rows" not in exported
      assert "tail_rows" not in exported
      assert "sample_values" not in json.dumps(exported)
      assert "sample-only-secret" not in json.dumps(exported)


  def test_export_serializes_undefined_statistics_as_null_and_strict_json():
      uploaded_file = UploadedFile(filename="empty.csv", content=b"value\n", file_type="csv")
      profile = build_profile_model(
          uploaded_file=uploaded_file,
          dataframe=pl.DataFrame({"value": pl.Series([], dtype=pl.Float64)}),
          read_time_ms=0,
          warnings=[],
      )

      text = serialize_profile_json(
          profile,
          datasetpeek_version="0.5.0",
          generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
      )

      assert "NaN" not in text
      assert "Infinity" not in text
      exported = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
      assert exported["numeric_summary"] == [
          {"name": "value", "min": None, "max": None, "mean": None, "median": None}
      ]


  @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
  def test_export_normalizes_non_finite_statistics(value):
      profile = make_profile()
      stats = replace(profile.numeric_columns[0], min=value, max=value, mean=value, median=value)
      profile = replace(profile, numeric_columns=[stats])
      text = serialize_profile_json(profile, datasetpeek_version="0.5.0")
      exported = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
      assert exported["numeric_summary"][0] == {
          "name": stats.name, "min": None, "max": None, "mean": None, "median": None
      }


  @pytest.mark.parametrize("source", [
      "s3://private-bucket/private-prefix/metrics.csv",
      "/private/uploads/metrics.csv",
      r"C:\private\uploads\metrics.csv",
  ])
  def test_export_exposes_only_source_basename(source):
      profile = make_profile()
      profile = replace(profile, file_summary=replace(profile.file_summary, filename=source))
      text = serialize_profile_json(
          profile,
          datasetpeek_version="0.5.0",
          generated_at=datetime(2026, 10, 29, tzinfo=timezone.utc),
      )

      exported = json.loads(text)
      assert exported["file"]["filename"] == "metrics.csv"
      assert "private" not in text
      assert set(exported) == {
          "schema_version", "metadata", "file", "columns", "numeric_summary",
          "signals", "orientation", "next_checks",
      }
  ```

- [ ] Add tests for a non-UTC aware timestamp, naive timestamp rejection, and default UTC timestamp bounded by before/after instants. Assert exact field sets for nested objects and representative signal/orientation/next-check content. Include a literal top value `NaN` to prove strings are retained; strict parsing, not substring bans, detects invalid numeric tokens.
- [ ] **Step 2: Run them and verify they fail** — `uv run pytest tests/test_profile_export.py -q`; expect collection failure because the serializer module does not exist.
- [ ] **Step 3: Implement the minimal serializer** — map `DatasetProfile` to the named top-level fields in the spec. Emit ratios as fractions, top-value strings/counts/caps, numeric statistics as JSON numbers or `null`, and signal objects with `column`, `kind`, and `message`. Do not serialize warnings, samples, source metadata paths/URIs, dataclasses, or view-model dictionaries. The current S3 reader stores the full URI in `FileSummary.filename`: normalize slash and backslash separators and export only its final filename component, without changing existing UI/report filenames. Do not redact legitimate dataset strings merely because they resemble paths or URIs. Defensively map non-finite numeric statistics to `None` before strict serialization. Normalize the timestamp to UTC ISO 8601 with `Z`; use `allow_nan=False`.
- [ ] **Step 4: Run focused verification** — `uv run pytest tests/test_profile_export.py -q`; expect all schema, privacy-boundary, timestamp, precision, cap, and strict-JSON tests to pass.

### Task 3: Add the Results-Page JSON Download

**Files:**
- Modify: `app/services/profiler.py`
- Modify: `app/templates/home.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Successful result view models include `profile_json`, generated by `serialize_profile_json` from the same `DatasetProfile` used for Markdown/HTML reports.
- The template embeds that string as JSON data and exposes an `Export JSON` button only inside the existing `{% if has_result %}` block.

- [ ] **Step 1: Write the failing tests** — add these assertions to `tests/test_app.py`:

  ```python
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
      assert "schema_version" in response.text
      assert "1.0.0" in response.text
      assert '"profile-model.json"' in response.text


  def test_upload_first_and_error_states_do_not_offer_json_download():
      client = RobynClient(create_app())

      home = client.get("/")
      error = client.post("/analyze", files={"dataset": {"filename": "bad.txt", "content": b"bad"}})

      assert home.status_code == 200
      assert error.status_code == 200
      assert 'id="download-json"' not in home.text
      assert 'id="download-json"' not in error.text
  ```

  The `.txt` upload is rejected by the existing file reader; also assert `Unsupported file type` appears in the error response.

- [ ] Add a payload round-trip regression: build a category containing `</script>`, quotes, Unicode, and a newline (within the configured display cap), render `/analyze`, extract only the `profile-json-data` script using an HTML parser, and decode twice: first the Jinja-embedded JSON string, then the exported document. Assert it matches the serialized profile data, contains the expected formatted top value, contains no preview/sample fields (including `sample_sets`), and has no literal closing-script sequence inside its data element. Do not assert absence of preview data across the whole page: previews are intentional UI content.
- [ ] Cover a successful S3 profile using the existing mocked S3 route pattern and assert its exported filename is only the basename. Cover empty upload rejection as well as unsupported extensions.
- [ ] **Step 2: Run them and verify they fail** — `uv run pytest tests/test_app.py::test_routes_render_profile_json_download_and_privacy_disclosure tests/test_app.py::test_upload_first_and_error_states_do_not_offer_json_download -q`; expect failures because no JSON export data or control exists yet.
- [ ] **Step 3: Implement the UI integration** — add `profile_json` to the successful view context using the serializer and current package-version helper. In `home.html`, add the button and concise disclosure that top values contain source data; embed `profile_json` via Jinja `tojson`; parse the embedded value and use the existing download helper with filename `profile-model.json` and MIME type `application/json;charset=utf-8`. Do not add an API route or expose JSON controls on empty/error states.
- [ ] **Step 4: Run focused verification** — `uv run pytest tests/test_app.py tests/test_profile_export.py -q`; expect the existing route/report tests and new download tests to pass.

### Task 4: Update User-Facing Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/PRD.md`

**Interfaces:**
- README describes JSON as an additional profile download, its schema version, and the top-value privacy boundary.
- PRD marks the export as delivered only when the feature and target release metadata are actually complete; retain the spec link as the contract reference.

- [ ] Update README capabilities and report-download documentation with `profile-model.json`, schema version `1.0.0`, and the top-value privacy disclosure; link to the design contract.
- [ ] Update PRD wording to distinguish implemented functionality from a published release. Preserve unrelated pending PRD edits; do not change package versions in this task.
- [ ] Review documentation against the implementation and spec. Do not add tests that pin prose or historical release numbers.
- [ ] Run `git diff --check` and `make check`; inspect untracked plan/spec files separately because ordinary `git diff` does not include them.

## Final Verification

- Use Task 4's successful `make check` as the final automated gate; rerun only if subsequent edits require it.
- Exercise actual browser downloads for local CSV and Parquet profiles: click Export JSON, inspect the saved bytes with a strict JSON parser, and assert filename `profile-model.json`, UTF-8 content, column order, numeric types, and absence of preview rows. Include the adversarial string fixture to verify it remains data. Check Markdown/HTML downloads still work.
- Verify S3 via the mocked route test; perform a live S3 browser check only with an already configured test object. If unavailable, record live S3 acceptance as unverified rather than requiring credentials or claiming coverage.
- Verify invalid uploads still show the existing validation message and no export controls.

## Completion Evidence

Record changed files, executed checks and results, browser download evidence, and any unverified acceptance cases. Keep changes uncommitted unless the user requests commits. This plan update does not start implementation.
