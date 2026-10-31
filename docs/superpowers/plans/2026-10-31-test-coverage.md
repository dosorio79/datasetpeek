# Targeted Test Coverage Implementation Plan

**Status:** Implemented locally; hosted browser evidence and publication pending.
**Goal:** Cover meaningful upload/S3 failures and one real browser journey.
**Architecture:** Extend existing pytest service/route tests; isolate an optional
Playwright Chromium smoke test from the fast suite. Measure coverage without quotas.
**Tech stack:** Existing Python 3.12, uv, pytest, Robyn, Polars; coverage.py and
optional Playwright. No Node or cloud test infrastructure.
**Spec:** [Targeted Test Coverage](../specs/2026-10-31-test-coverage-design.md)
**Progress:** [implementation record](2026-10-31-test-coverage-progress.md)

Use the executing-plans workflow when authorized. Preserve the current uncommitted
quality/security implementation. No commits, remote settings, or branch changes
without authorization; implement in place unless isolation provides a concrete benefit.

## Global constraints

- Synthetic inputs, mocked S3, loopback-only owned browser server; no secrets.
- Default tests exclude browser and must collect without Playwright installed.
- One Chromium journey; no percentage gates or broad refactors.
- Do not change the four required branch checks or deploy anything.
- Tests for existing correct behavior may pass immediately; do not manufacture
  failures. Any actual production fix needs a reproducing failing regression first.

## Review focus

- Stable app assertions survive changes in third-party parser error text (task 1).
- Streaming limits work without trustworthy Content-Length (task 2).
- Local credentials/settings never enter browser fixtures or diagnostics (task 3).
- Broken JavaScript is observable; byte/string assertions alone are insufficient (task 3).
- Browser failures do not leak processes or silently skip in CI (tasks 3–4).

## Task 1: File-reader failure cases

**Files:** Create `tests/test_file_reader_errors.py`; extend
`tests/test_csv_delimiters.py` and relevant tests in `tests/test_app.py`.
Modify `app/services/file_reader.py` only for the coverage exclusion or a
reproduced defect.

- [x] Record Git state and run `make check` as the baseline.
- [x] Add parameterized `test_invalid_file_reports_validation_error` for corrupt
  Parquet, controlled parser failure, and header-only CSV. Assert exception type
  and stable prefix/filename or no-rows message, not Polars internals.
- [x] Add `test_invalid_multipart_is_rejected` for missing boundary, filename,
  dataset part, empty dataset bytes, unsupported extension/body. Exercise
  `UploadedFile.from_request_files`; use minimal request objects with body/headers.
- [x] Add `test_upload_wrapper_preserves_bytes` for bytearray body and supported
  content/body/data wrappers; avoid repeating existing successful multipart cases.
- [x] Add delimiter/tolerant fallback cases with explicit expected dataframe
  values and warnings. Inject parser errors only where required to reach a branch;
  preserve a real-parser case for each successful fallback being asserted.
- [x] Extend a route test to assert invalid input renders an error with no report
  controls and no 500. Run the focused tests and inspect any failure's cause.
- [x] Remove the `pragma: no cover` on the parse-exception handler. If behavior
  is wrong, fix minimally after observing the failing test; otherwise no production edit.
- [x] Run `uv run --locked pytest tests/test_file_reader_errors.py tests/test_csv_delimiters.py tests/test_app.py -q`.
  Expected: all pass with no cloud requests.

## Task 2: S3 failure and size-limit contracts

**Files:** Extend `tests/test_s3_reader.py` and S3 adapter/route cases in
`tests/test_app.py`. Modify `app/services/s3_reader.py` only for demonstrated bugs.

- [x] Add a small local fake response context manager exposing headers and
  `read(size)`; record requested size/read calls, without a general mock framework.
- [x] Add `test_s3_length_limit_before_read`, `test_s3_stream_limit_without_trusted_length`,
  and `test_s3_accepts_exact_limit`: advertised overflow must avoid reading;
  missing/understated length reads at most limit+1 and rejects oversize; exact limit succeeds.
- [x] Add `test_s3_passes_configured_timeout` by capturing the urllib call.
  Add timeout/URLError exhaustion tests asserting stable S3ReadError messages.
- [x] Parameterize authenticated 403, 404, and 500 errors, with sentinel sensitive
  values in the injected error URL/text. Assert correct message category and no sentinels.
- [x] Add `test_s3_alternate_url_success` and exhaustion/nonretryable-error cases;
  verify bounded attempts and returned bytes, not timing or real AWS behavior.
- [x] Extend adapter/route tests to verify S3ReadError → FileValidationError →
  rendered error without exports. Run `uv run --locked pytest tests/test_s3_reader.py tests/test_app.py -q`.
  Expected: all pass; only the existing loopback HTTP integration uses a socket.

## Task 3: Optional Chromium smoke test

**Files:** Modify `pyproject.toml`, `uv.lock`, `.gitignore`, `Makefile`;
create `tests/browser/conftest.py` and `tests/browser/test_reports.py`.

- [x] Add `playwright` in group `browser`, leaving runtime packages unchanged.
  Register marker `browser`; set default pytest selection to `-m 'not browser'`.
  Use imports inside fixtures so missing optional tooling does not break collection.
- [x] Implement `app_url` fixture (yield loopback URL) with a temporary synthetic
  environment, available port, owned subprocess of `sys.executable main.py`,
  bounded health polling/port retry, and unconditional terminate/wait cleanup.
  Do not kill unknown processes. Capture logs without credentials.
- [x] Implement `browser_page` fixture using sync Playwright/Chromium with
  downloads enabled, bounded waits, page-error collection, and unconditional
  teardown. On failure save synthetic-only screenshot and relevant server log.
- [x] Write `test_upload_cycle_and_download_reports` following all five spec
  steps. Generate CSV with 30 unique IDs, repeated `<b>literal</b>` cells, and
  test sample size 3. Use existing selectors, `expect_download`, and actual bytes.
  Derive/check the expected deterministic sample sequence rather than assuming
  arbitrary samples differ. Record the initial rows and verify wraparound.
- [x] Track `/analyze` requests after result render to ensure sample cycling and
  downloads remain client-side. Assert no uncaught page errors or injected DOM.
- [x] Add `make browser-test` using
  `uv run --locked --group browser pytest tests/browser -m browser -q`.
  Document separate one-time `uv run --locked --group browser playwright install chromium`.
- [x] Run once in Chromium; if it exposes a defect, preserve a failing regression
  before the minimal repair. Temporarily disable a download/cycling handler in
  an isolated copy, demonstrate the smoke test fails, restore, and rerun.
- [x] Confirm failure cleanup leaves no owned child process. Confirm default
  pytest still collects/runs successfully in a dev-only environment.

## Task 4: Coverage reporting, CI, and contributor documentation

**Files:** Modify `pyproject.toml`, `uv.lock`, `Makefile`, `.gitignore`,
`.github/workflows/ci.yml`, `CONTRIBUTING.md`, `README.md`, and `agents.md`.

- [x] Add `coverage` to dev dependencies; set branch measurement and source
  `app`, `main` in pyproject. Add `make coverage` using:

```bash
uv run --locked coverage run -m pytest -q
uv run --locked coverage report -m
uv run --locked coverage json -o coverage.json
```

- [x] Ignore generated coverage/browser outputs. Keep `make check` fast and
  browser-free; do not introduce coverage fail-under or a hosted dashboard.
- [x] Replace CI test invocation with coverage measurement/reporting, keeping
  job name `test` and one pytest execution. Reports must not hide pytest failure.
- [x] Add `browser-smoke` job: same existing events/read-only permissions,
  ten-minute timeout, pinned actions, uv 0.11.19/Python 3.12,
  `uv sync --locked --group dev --group browser`,
  `uv run --locked --group browser playwright install --with-deps chromium`,
  then `make browser-test`. No secrets or automatic test retries.
- [x] Document optional browser setup, direct commands/Windows caveats, coverage
  scope and line-versus-branch interpretation. Note that hosted browser success
  and any future required-check rollout remain separate evidence.
- [x] Run `make check`, `make coverage`, `make browser-test`, and `make audit`.
  Validate workflow with actionlint and inspect dependency diff for unintended upgrades.
- [x] Compare line/branch counts for file/S3 modules against the recorded
  baseline; list residual meaningful gaps. Do not promise a specific percentage.
- [x] Review tests for behavioral assertions rather than implementation mirroring,
  cleanup, and excessive mocking. Record actual local results and hosted checks
  still pending; no remote publication or protection changes in this plan.
