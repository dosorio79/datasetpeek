# Targeted test coverage implementation progress

Plan: [2026-10-31-test-coverage.md](2026-10-31-test-coverage.md)
Spec: [2026-10-31-test-coverage-design.md](../specs/2026-10-31-test-coverage-design.md)

- User authorized continuing implementation; local changes only, no commit, push,
  deployment, or remote GitHub setting changes.
- Work stayed on `dev` and preserved the uncommitted repository
  quality/security implementation and planning documents.
- Baseline: the partial test work failed formatting and six upload-wrapper cases.
  Those tests used an unrealistic flat `files` mapping. They were corrected to
  the existing nested upload shape; no production defect was involved.

## Task 1 - complete

- Completed file-reader failure coverage for corrupt Parquet, injected parser
  failure, header-only CSV, invalid multipart bodies, unsupported uploads, and
  supported dict/attribute byte wrappers (including bytearray bodies).
- Added delimiter fallback coverage for undetected delimiters, tolerant CSV
  parsing, and a synthetically injected non-comma parse failure.
- Extended the invalid-upload route test to assert no export, sample-cycling, or
  sample-table controls are rendered.
- Removed the parser-exception `pragma: no cover`; the injected parser test
  exercises the handler. Focused Task 1 run: 60 passed.

## Task 2 - complete

- Added a minimal local fake response context manager and recorded bounded reads.
- Covered advertised overflow before read, missing/understated Content-Length,
  exact-limit acceptance, configured timeout propagation, and stable transport
  exhaustion messages.
- Covered authenticated 403, 404, and 500 errors with synthetic endpoint,
  signature, token, credential, and error sentinels; none leak into user-facing
  messages.
- Covered alternate-URL success, bounded retry exhaustion, and nonretryable
  server errors. Adapter and route tests confirm `S3ReadError` becomes a rendered
  `FileValidationError` state without report controls. Focused Task 2 run:
  60 passed.

## Task 3 - complete

- Added optional `browser` dependency group with Playwright 1.64.1 and a
  `browser` marker. Default pytest selection is `-m 'not browser'`.
- Added session-named fixtures that select a loopback port, retry startup, sanitize
  AWS/DatasetPeek environment settings, own and terminate the server process,
  poll `/health`, collect page errors, and save synthetic failure diagnostics.
- Added one real Chromium journey for upload, deterministic sample cycling,
  literal HTML rendering, all three downloads, report content, client-side-only
  behavior, and uncaught page errors.
- The browser journey exposed a real column-order defect: client-rendered samples
  derived column order from alphabetized JSON keys, so columns reordered after
  cycling. A service-level regression failed first (`KeyError: 'columns'`), then
  an explicit ordered `columns` list was added to the browser sample payload.
- Negative control: in an isolated `/tmp` copy, changing the Markdown download
  filename made the smoke test fail on `broken-report.md`; no owned server
  process remained after cleanup. The real tree was not modified for this check.
- Review hardening: sanitized `ROBYN_*` startup overrides (reproduced as a
  45-second setup failure with `ROBYN_PORT=1`), detached the child from inherited
  stdin, required a child startup marker before accepting `/health`, included
  server log tails in startup diagnostics, wrote failure artifacts per test, and
  asserted exactly one `/analyze` POST before cycling plus no additional POSTs
  after cycling or downloads.
- Default collection in a Playwright-free environment: 125 passed, 1 deselected.
  Browser run: 1 passed; hostile `ROBYN_HOST`/`ROBYN_PORT` run: 1 passed.

## Task 4 - complete locally; hosted evidence pending

- Added `coverage` 7.17.0 to dev, branch measurement for `app` and `main`, and
  `make coverage` (text + JSON, no fail-under).
- CI `test` now runs one covered pytest execution and reports text/JSON coverage.
  Added `browser-smoke` with pinned actions, read-only permissions, a ten-minute
  timeout, locked dev+browser sync, Chromium with OS dependencies, and no secrets
  or retry masking. It is not a fifth required branch-protection context.
- Updated README, CONTRIBUTING, and agent guidance for optional browser setup,
  Windows direct commands, coverage scope, and hosted-evidence boundaries.
- `uv lock` added coverage, playwright, greenlet, and pyee; existing resolved
  versions were preserved. Generated coverage/browser output is ignored.
- `actionlint` 1.7.12 validated the workflow.

### Measured coverage

Current run: 125 tests, 953/1,027 lines (92.8%), 304/368 branches (82.6%);
coverage.py combined percentage is 90%. Baseline in the spec was 901/1,025
(87.9%) lines and 269/368 (73.1%) branches.

| Module | Lines | Branches | Spec baseline |
| --- | --- | --- | --- |
| `file_reader.py` | 221/261 (84.7%) | 95/136 (69.9%) | 70.7% / 51.5% |
| `s3_reader.py` | 136/142 (95.8%) | 36/42 (85.7%) | 85.9% / 61.9% |
| `profile_export.py` | 35/36 (97.2%) | 11/12 (91.7%) | 97.2% / 91.7% |

Residual meaningful gaps: S3-URI error/empty-object translation, CSV comma-retry
failure and unsupported-delimiter scoring branches, some multipart header/
fallback shapes, S3 path-style/session-token/invalid-endpoint configuration, and
root server startup. Browser JavaScript and the inline workflow policy remain
outside Python coverage; existing policy tests execute that policy separately.
No quota or percentage promise is implied.

### Verification actually run

- `make check`: Ruff, formatting, mypy, and 125 tests passed.
- `make coverage`: 125 passed, report and JSON generated.
- `make browser-test`: 1 Chromium journey passed.
- `make audit`: 32 installed packages compatible; 33 audited packages with no
  known vulnerabilities or adverse statuses.
- Hosted `browser-smoke` success, publication, and any future required-check
  rollout remain unverified and separately authorized.
