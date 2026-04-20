<picture>
  <source media="(prefers-color-scheme: dark)" srcset="app/img/datapeek-logo-readme-dark.png">
  <img src="app/img/datapeek-logo.png" alt="DataPeek logo" width="420">
</picture>

[![CI](https://github.com/dosorio79/datapeek/actions/workflows/ci.yml/badge.svg)](https://github.com/dosorio79/datapeek/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.1-informational)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)

Fast, minimal profiler for CSV and Parquet files.

DataPeek is a small server-rendered app built with Robyn, Polars, and Jinja2. It gives a technical user a quick first-pass read on a dataset without turning the UI into a full EDA tool.

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

## Render Deployment

`render.yaml` configures DataPeek as a single Render web service on Render's `free` plan.

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
- Keep uploads modest in size. The app will warn on larger files, but this MVP is not optimized for large datasets or concurrent heavy uploads.
