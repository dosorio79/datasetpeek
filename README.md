<img src="app/img/datasetpeek-icon-source.png" alt="DatasetPeek icon" width="120">

# DatasetPeek

[![CI](https://github.com/dosorio79/datasetpeek/actions/workflows/ci.yml/badge.svg)](https://github.com/dosorio79/datasetpeek/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.5.0-informational)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)

Fast, minimal profiler for CSV and Parquet files.

DatasetPeek is a small server-rendered app built with Robyn, Polars, and Jinja2. It gives a technical user a quick first-pass read on a local, S3, or MinIO dataset without turning the UI into a full EDA tool.

## Current Capabilities

- Local and S3-compatible CSV/Parquet profiling.
- Deterministic orientation summary and lightweight next-check guidance.
- Column role hints, quality signals, capped top values, and numeric summaries.
- Random sample cycling plus head and tail previews.
- Markdown and standalone HTML report downloads generated from the in-memory profile.
- Versioned `profile-model.json` export for downstream tools and automation.
- Running app version shown in the page footer.
- Demo-friendly social preview metadata for shared app links.

## Setup

Requirements:
- Python 3.12+
- `uv`

Install dependencies:

```bash
make install
```

## Run

Start the app:

```bash
make run
```

Open `http://127.0.0.1:8080`.

The launcher also respects `PORT` and `HOST`, which is useful for managed platforms:

```bash
PORT=9090 HOST=0.0.0.0 uv run python main.py
```

DatasetPeek accepts local CSV/Parquet uploads and S3-compatible object URIs. Use the source switcher on the home page to choose between a local file and an `s3://` object:

```text
s3://bucket/path/data.csv
```

For private AWS S3, MinIO, Cloudflare R2, or another S3-compatible object store, configure read-only credentials through environment variables:

```bash
DATASETPEEK_S3_ENDPOINT_URL=http://localhost:9000  # MinIO/custom S3/R2 endpoint
DATASETPEEK_S3_ACCESS_KEY_ID=minioadmin
DATASETPEEK_S3_SECRET_ACCESS_KEY=minioadmin
DATASETPEEK_S3_REGION=us-east-1
DATASETPEEK_S3_FORCE_PATH_STYLE=true
```

If `DATASETPEEK_S3_ENDPOINT_URL` is set, DatasetPeek uses path-style requests such as `http://localhost:9000/bucket/path/data.csv`, which matches MinIO's default setup and many S3-compatible providers. Without credentials, DatasetPeek attempts anonymous reads, but public S3 bucket behavior is provider- and policy-dependent.

DatasetPeek profiles the full uploaded file or S3 object when it is within the size limit. If the object is an exported sample from a larger dataset, the reported rows, signals, and summaries describe that sample.

Legacy `DATAPEEK_*` environment variables are still accepted as fallbacks during the rename.

## Operational Settings

DatasetPeek reads operational settings from environment variables at runtime:

| Setting | Default | Purpose |
| --- | ---: | --- |
| `DATASETPEEK_MAX_UPLOAD_MB` | `100` | Reject uploads or S3 objects above this size. |
| `DATASETPEEK_LARGE_FILE_WARNING_MB` | `50` | Show a large-file warning above this size. |
| `DATASETPEEK_RANDOM_SAMPLE_ROWS` | `10` | Number of rows in each random sample preview. |
| `DATASETPEEK_HEAD_TAIL_ROWS` | `5` | Number of rows shown in head and tail previews. |
| `DATASETPEEK_SAMPLE_VALUE_COUNT` | `3` | Number of sample values shown per column. |
| `DATASETPEEK_TEXT_TRUNCATE_CHARS` | `50` | Maximum displayed length for cell/sample text. |
| `DATASETPEEK_TOP_VALUES_LIMIT` | `5` | Maximum top values shown for compact categorical/flag fields. |
| `DATASETPEEK_CSV_INFER_SCHEMA_ROWS` | `5000` | Number of CSV rows Polars scans for schema inference. |
| `DATASETPEEK_S3_DOWNLOAD_TIMEOUT_SECONDS` | `30` | Timeout for S3-compatible object downloads. |

## Profile Model JSON

The results page offers an **Export JSON** download alongside the Markdown and
HTML reports. The downloaded `profile-model.json` is a compact, versioned
contract for downstream tooling:

- `schema_version` is `1.0.0` and identifies the export schema independently of
  the app version.
- File summary, columns, inferred roles, ratios, capped top values, numeric
  summaries, signals, orientation, and next checks are included.
- The exported `file.filename` is the basename; S3 URIs and local paths are not
  included.
- Ratios are JSON numbers in the range `0`–`1`; undefined numeric statistics are
  `null`.
- Preview rows, head/tail rows, and per-column sample values are excluded.
- Capped top values and signal messages can include dataset content. Review the
  file before sharing it.
- `metadata.generated_at` records when the export was generated.

See [`docs/superpowers/specs/2026-10-29-profile-model-json-design.md`](docs/superpowers/specs/2026-10-29-profile-model-json-design.md)
for the full schema and compatibility rules.

## Test

Run the fast test suite:

```bash
make test
```

Run the local fast/quality checks (Ruff lint, format, type checks, and unit tests):

```bash
make check
```

Measure line and branch coverage for `app` and `main.py`:

```bash
make coverage
```

The default suite excludes the `browser` marker and collects without optional
Playwright tooling. The Chromium journey is optional, much slower than
`make check`, downloads a browser on first setup, and is not part of the fast
quality command. Coverage has no fail-under threshold, does not measure
JavaScript execution or the inline workflow policy, and reports lines and
branches separately. The combined percentage is not line coverage.

Run the real Chromium upload/download journey after installing the optional
browser group and browser once:

```bash
uv sync --locked --group dev --group browser
uv run --locked --group browser playwright install chromium
make browser-test
```

On Windows without `make`, run
`uv run --locked --group browser pytest tests/browser -m browser -q` instead.
Browser tests start and stop their own loopback-only server and do not use
cloud credentials or production data. CI runs them in a separate
`browser-smoke` job; a green local run is not hosted CI evidence.

## Repo Layout

```text
app/
  main.py              Robyn app setup and route registration
  routes/              HTTP handlers
  services/            File loading, profiling, heuristics, and view-model assembly
  templates/           Jinja templates
  static/              CSS and browser assets
app/img/               Logo and icon source assets
tests/                 Route, service, delimiter, and storage tests
docs/PRD.md            Product requirements
docs/branch-protection-plan.md
                       Terraform-managed GitHub branch protection policy
infra/github/          Terraform for GitHub repository settings
agents.md              Repository guidance for coding agents
main.py                Thin root launcher
Makefile               Common developer commands
```

## Common Commands

```bash
make install   # sync dependencies
make run       # start the Robyn app
make test      # run pytest (browser tests excluded)
make check     # Ruff lint/format check, mypy, pytest
make coverage  # branch coverage report for app and main.py
make browser-test # optional Chromium upload/download smoke test
make audit     # dependency compatibility and known vulnerabilities (network)
make clean     # remove pytest and Python cache files
```

## Repository Operations

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and collaboration: branch from
`dev`, open feature PRs into `dev`, and let the maintainer release through a
`dev` → `master` PR. The quality/security checks are implemented locally; remote CI activation and
collaborator protections still require publication and the documented rollout.

GitHub branch protection is managed with Terraform in `infra/github`.
The prepared policy requires PRs and four checks on `dev` and `master`, with
zero mandatory approvals. It has not been applied; see the rollout prerequisites
below. Fork-only access keeps upstream merging under the maintainer’s control.

See [docs/branch-protection-plan.md](docs/branch-protection-plan.md) for the policy and apply workflow, and [SECURITY.md](SECURITY.md) for security reporting and scan status.

## Render Deployment

`render.yaml` configures DatasetPeek as a single Render web service on Render's `free` plan.

- Health check: `/health`
- Build command: `pip install uv && uv sync --locked`
- Start command: `uv run python main.py`
- Python version: `3.12.10`

Operational assumptions for this deployment:

- Uploads are processed in-request; preview sample sets are embedded in the rendered response.
- Restart, redeploy, crash, or free-tier spin-down clears any in-flight request state.
- The service should stay at a single instance unless upload state is moved out of memory.
- Render free web services spin down after 15 minutes of inactivity, so the first request after idle can take about a minute to recover.
- Free web services do not support persistent disks or scaling beyond a single instance.
- Keep uploads modest in size. The app warns above 50 MB and rejects uploads above 100 MB.
- Configure S3-compatible credentials in Render environment variables; Render does not read your local `.env` file.
