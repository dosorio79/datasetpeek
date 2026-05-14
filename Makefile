PYTHON := uv run python
PYTEST := uv run pytest

.PHONY: install run test check clean

install:
	uv sync --group dev

PORT ?= 8080

run:
	$(PYTHON) main.py --port $(PORT)

test:
	$(PYTEST) -q

check:
	$(PYTEST) -q
	$(PYTHON) -m py_compile main.py app/main.py app/routes/home.py app/routes/profile.py app/services/file_reader.py app/services/heuristics.py app/services/profiler.py app/services/s3_reader.py app/services/session_store.py app/services/settings.py

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
