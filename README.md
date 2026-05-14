<img src="app/img/datasetpeek-icon-source.png" alt="DatasetPeek icon" width="120">

# DatasetPeek

[![CI](https://github.com/dosorio79/datasetpeek/actions/workflows/ci.yml/badge.svg)](https://github.com/dosorio79/datasetpeek/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.3.0-informational)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)

Fast, minimal profiler for CSV and Parquet files.

DatasetPeek is a small server-rendered app built with Robyn, Polars, and Jinja2. It gives a technical user a quick first-pass read on a local, S3, or MinIO dataset without turning the UI into a full EDA tool.

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

## Test

Run the test suite:

```bash
make test
```

Run tests plus bytecode compilation checks:

```bash
make check
```

## Repo Layout

```text
app/
  main.py              Robyn app setup and route registration
  routes/              HTTP handlers
  services/            File loading, profiling, heuristics, in-memory resample store
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
make test      # run pytest
make check     # run tests and py_compile
make clean     # remove pytest and Python cache files
```

## Repository Operations

GitHub branch protection is managed with Terraform in `infra/github`.
The current solo-maintainer policy requires PRs and the `test` CI check for `master`, without requiring a second approving reviewer.

See [docs/branch-protection-plan.md](docs/branch-protection-plan.md) for the policy and apply workflow.

## Render Deployment

`render.yaml` configures DatasetPeek as a single Render web service on Render's `free` plan.

- Health check: `/health`
- Build command: `pip install uv && uv sync --locked`
- Start command: `uv run python main.py`
- Python version: `3.12.10`

Operational assumptions for this deployment:

- Uploads and resample tokens are stored in process memory only.
- Restart, redeploy, crash, or free-tier spin-down clears uploaded file state.
- The service should stay at a single instance unless upload state is moved out of memory.
- Render free web services spin down after 15 minutes of inactivity, so the first request after idle can take about a minute to recover.
- Free web services do not support persistent disks or scaling beyond a single instance.
- Keep uploads modest in size. The app warns above 50 MB and rejects uploads above 100 MB.
- Configure S3-compatible credentials in Render environment variables; Render does not read your local `.env` file.
