# Targeted Test Coverage — Design Spec

**Status:** Proposed; documentation only, implementation not authorized.
**Date:** 2026-10-31
**Depends on:** The locally implemented repository quality/security changes.

## Goal and evidence

Close meaningful failure-path gaps and prove that the browser can download
reports and cycle samples. Preserve the small project workflow; no coverage
quota, cross-browser matrix, cloud test service, or broad application refactor.

The preceding measured run passed 87 tests. Python application line coverage
was 901/1,025 (87.9%); branch coverage was 269/368 (73.1%). File reading had
70.7% line / 51.5% branch coverage; S3 reading 85.9% / 61.9%; JSON export
97.2% / 91.7%. These describe that run, not a target or current guarantee.
Coverage excludes JavaScript execution and the inline workflow policy. Existing
policy tests separately execute that policy. Parser exceptions currently use
`pragma: no cover`, so the baseline understates that gap.

## Approach

Add focused pytest cases at existing public service boundaries and one real
Chromium journey. Reuse existing synthetic fixtures and RobynClient tests.
Most new failure tests use local byte payloads or mocked urllib responses;
retain the existing local HTTP S3 integration test. No external S3 account,
production credentials, fixed port, or real user dataset.

Alternatives considered: coverage-only reporting would not test browser
behavior; a broad end-to-end suite adds disproportionate setup and flakiness.
The proposed middle ground adds `coverage` to dev tools and `playwright` to a
separate `browser` dependency group. Use Playwright's synchronous Python API
inside pytest fixtures, without an additional pytest plugin or Node toolchain.
Select compatible versions during implementation and lock them with uv.

## File-reader contracts

Add cases covering these outcomes, not every internal branch:

- Corrupt Parquet and a parser failure become `FileValidationError`; assert the
  stable `Could not parse` prefix and filename, not exact Polars wording.
  Remove the parser-exception coverage exclusion once exercised.
- Header-only CSV is rejected as having no rows. Unsupported filenames and
  empty dataset multipart parts receive the existing validation messages.
- Multipart metadata recovery must select the `dataset` part; missing boundary,
  missing filename, absent dataset part, or unsupported body representation must
  not cause a server error. Valid bytearray bodies and supported upload wrappers
  still produce bytes. Reuse existing multipart tests rather than duplicating them.
- Delimiter detection fallback and tolerant CSV parsing preserve rows and emit
  appropriate warnings. Use real small CSV payloads for observable behavior;
  narrowly inject parser failures to reach otherwise version-dependent branches.
- Add one route-level invalid-upload assertion: user-facing error, no export
  controls, no 500. Existing error-state tests may be extended rather than copied.

Inspection found `_read_csv` attempts a comma retry after a non-comma failure
but still runs the tolerant comma parse afterward. Do not freeze parser call
counts as the contract or change this behavior speculatively. If a new test
shows data loss or a misleading result, reproduce it first and make only the
minimal correction; record any broader design question separately.

## S3 contracts

Mock the transport (`s3_reader.urlopen`) with small context-manager responses
for bounded reads; mock `read_s3_url` only for orchestration cases.

- A configured timeout reaches urllib. Timeout/URLError exhaustion yields
  `S3ReadError`, no raw transport traceback in user-facing output.
- An advertised length above the limit is rejected before reading. With absent
  or understated length, read at most `max_bytes + 1`, then reject oversize.
  Exactly `max_bytes` is accepted. Use byte-scale limits, not huge fixtures.
- Authenticated 403, 404, and other HTTP errors yield the existing appropriate
  messages. Include synthetic endpoint/query/credential sentinels in the fake
  transport error and assert none leak into the returned error message.
- For ordinary AWS-style URLs, a retryable first failure can use the alternate
  URL and succeed. Exhaustion produces the final user-facing error; a server
  error outside the existing retry set does not retry indefinitely.
- The upload adapter translates `S3ReadError` to `FileValidationError`; a route
  error renders without export actions. No live cloud request is needed.

Malformed Content-Length handling, redirect/SSRF policy, credential signing
redesign, and retry-policy changes are outside this test-focused scope. Report
any demonstrated defects rather than silently broadening the work.

## One browser journey

Use a single `test_upload_cycle_and_download_reports` against a real locally
started Robyn process and headless Chromium. Upload a generated synthetic CSV
with 30 unique IDs and a short inert HTML-looking cell such as `<b>literal</b>`.
Set sample size to 3 and keep deterministic existing sample seeds.

1. Before upload, export controls are absent. Upload through `#dataset` and
   click `#analyze-submit`; wait for the results using locator assertions.
2. Observe `#sample-set-label` and `#sample-table tbody`; click `#next-sample`
   and verify the label and displayed IDs change. Cycle through all available
   sample sets and verify the initial label/rows return. Do not assume random
   rows differ without a deliberately chosen fixture; assert deterministic IDs.
3. Verify the HTML-looking cell renders literally and never becomes a `b`
   element in the sample table, including after cycling.
4. Click all three export buttons with `page.expect_download`. Verify exact
   filenames: `profile-model.json`, `datasetpeek-report.md`, and
   `datasetpeek-report.html`. Read saved bytes before closing the context.
   JSON must parse, match source row/column counts, carry schema version 1.0.0,
   and omit preview/sample fields. Markdown/HTML must contain the dataset name
   and meaningful report headings; avoid whole-file snapshots and timestamps.
5. After the initial analysis completes, downloads and sample cycling must not
   issue another `/analyze` request. Fail on uncaught page exceptions.

Browser fixtures own their subprocess, port, context, and cleanup. Bind only
loopback; select an available port and handle the selection/start race with a
bounded retry. Poll `/health` with a 15-second deadline and check process exit;
never accept a pre-existing server as this fixture's process. Use bounded
Playwright waits, not arbitrary sleeps. Terminate/wait only the owned child
(and its owned process group if needed); close browsers even on assertion failure.
Sanitize child environment: remove AWS/S3 credentials and legacy/app settings,
then provide known test settings so local configuration cannot change results.

## Local and CI integration

- Register a `browser` pytest marker; default pytest selection excludes it.
  Keep Playwright imports inside browser-only fixtures so ordinary collection
  works without the optional group. Explicit browser runs must fail with setup
  guidance if tooling is absent, never silently skip.
- `make check` stays fast. Add `make coverage` (coverage.py branch measurement
  for `app` and root `main.py`, pytest excluding browser, text + JSON reports)
  and `make browser-test` (explicit browser selection, optional group enabled).
- Configure coverage in pyproject; ignore `.coverage*`, `coverage.json`,
  `htmlcov/`, and browser failure outputs. Report lines and branches separately;
  coverage.py's combined percentage must not be labeled line coverage.
- Existing CI `test` job runs under coverage instead of running pytest twice.
  Print report in logs, produce JSON; no external dashboard or fail-under gate.
- Add a separate `browser-smoke` CI job on the existing workflow events,
  Python 3.12/uv 0.11.19, locked dev+browser sync, and Chromium-only installation
  with OS dependencies. Reuse verified pinned actions and read-only permissions.
  Ten-minute timeout, no secrets, no retries that hide a failing test.
- Start as a visible CI check, not a new Terraform-required context. Do not
  silently alter the four-check branch protection rollout already prepared.
- Capture synthetic-only screenshot/server diagnostics on browser failure into
  ignored local output; include useful errors in CI logs. Artifact uploading
  and traces are optional later, not another action/dependency in this slice.
- Update CONTRIBUTING.md, README command descriptions, and agent guidance.
  Explain browser installation, separate runtime cost, and coverage limitations.

## Acceptance

The targeted failure cases pass, existing tests stay green, the real Chromium
journey passes, and fast tests run without Playwright installed. Demonstrate
that a deliberately broken browser interaction causes the smoke test to fail,
then restore and rerun. Compare measured file/S3 branch coverage with the
baseline, explain remaining gaps, and do not claim a numeric improvement before
measurement. Review any necessary production fix separately from test additions.
No implementation, commits, remote activation, or release is authorized here.

## References

- [Playwright Python library](https://playwright.dev/python/docs/library)
- [Download assertions](https://playwright.dev/python/docs/downloads)
- [Chromium installation and CI](https://playwright.dev/python/docs/ci)
- [Coverage.py](https://coverage.readthedocs.io/)
