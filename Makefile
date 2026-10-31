PYTHON := uv run --locked python
PYTEST := uv run --locked pytest

.PHONY: install run test check audit coverage browser-test clean

install:
	uv sync --locked --group dev

PORT ?= 8080

run:
	$(PYTHON) main.py --port $(PORT)

test:
	$(PYTEST) -q

check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked mypy app main.py
	$(PYTEST) -q

coverage:
	uv run --locked coverage run -m pytest -q
	uv run --locked coverage report -m
	uv run --locked coverage json -o coverage.json

browser-test:
	uv run --locked --group browser pytest tests/browser -m browser -q

audit:
	uv pip check --python "$$($(PYTHON) -c 'import sys; print(sys.executable)')"
	uv audit --locked --python-version 3.12 --python-platform linux

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
