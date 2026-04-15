<picture>
  <source media="(prefers-color-scheme: dark)" srcset="app/img/datapeek-logo-readme-dark.png">
  <img src="app/img/datapeek-logo.png" alt="DataPeek logo" width="420">
</picture>

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
