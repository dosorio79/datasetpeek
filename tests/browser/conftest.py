from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
FAILURE_DIR = ROOT / "test-results" / "browser"
HEALTH_TIMEOUT_SECONDS = 15
SENSITIVE_ENV_PREFIXES = ("AWS_", "DATASETPEEK_", "DATAPEEK_", "ROBYN_")


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _test_environment(port: int) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(SENSITIVE_ENV_PREFIXES)
    }
    env.update(
        {
            "HOST": "127.0.0.1",
            "PORT": str(port),
            "DATASETPEEK_RANDOM_SAMPLE_ROWS": "3",
        }
    )
    return env


def _stop_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_for_health(url: str, process: subprocess.Popen[bytes], log_path: Path) -> None:
    from urllib.error import URLError
    from urllib.request import urlopen

    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before becoming healthy:\n{_log_tail(log_path)}")
        try:
            with urlopen(f"{url}/health", timeout=1) as response:
                if response.status == 200 and response.read() == b'{"status":"ok"}':
                    if f"Starting server at {url}" in _log_text(log_path):
                        return
        except (OSError, URLError):
            pass
        time.sleep(0.1)
    raise RuntimeError(
        f"Server did not become healthy within {HEALTH_TIMEOUT_SECONDS}s:\n{_log_tail(log_path)}"
    )


def _log_text(log_path: Path) -> str:
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _log_tail(log_path: Path, limit: int = 4000) -> str:
    return _log_text(log_path)[-limit:] or "<server log unavailable>"


@pytest.fixture
def app_server(request):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", request.node.name)
    run_dir = FAILURE_DIR / safe_name
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "server.log"
    process: subprocess.Popen[bytes] | None = None
    log_file = None
    last_error: Exception | None = None

    try:
        for _ in range(3):
            port = _available_port()
            url = f"http://127.0.0.1:{port}"
            log_file = log_path.open("w", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, "main.py", "--host", "127.0.0.1", "--port", str(port)],
                cwd=ROOT,
                env=_test_environment(port),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            try:
                _wait_for_health(url, process, log_path)
            except RuntimeError as exc:
                last_error = exc
                _stop_owned_process(process)
                process = None
                log_file.close()
                log_file = None
                continue

            yield SimpleNamespace(url=url, log_path=log_path, run_dir=run_dir, process=process)
            return

        raise RuntimeError(
            f"Could not start DatasetPeek for browser testing:\n{_log_tail(log_path)}"
        ) from last_error
    finally:
        if process is not None:
            _stop_owned_process(process)
        if log_file is not None:
            log_file.close()


@pytest.fixture
def app_url(app_server):
    return app_server.url


@pytest.fixture
def browser_page(request, app_server):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail(
            "Playwright is not installed. Run: uv sync --locked --group dev --group browser",
            pytrace=False,
        )

    page_errors: list[str] = []
    playwright = sync_playwright().start()
    try:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:
            message = str(exc)
            if (
                "executable doesn't exist" in message.lower()
                or "executable not found" in message.lower()
            ):
                pytest.fail(
                    "Chromium is not installed. Run: "
                    "uv run --locked --group browser playwright install chromium",
                    pytrace=False,
                )
            raise

        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(10_000)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        try:
            yield page, page_errors
        finally:
            failed = any(
                report is not None and report.failed
                for report in (
                    getattr(request.node, "rep_setup", None),
                    getattr(request.node, "rep_call", None),
                    getattr(request.node, "rep_teardown", None),
                )
            )
            if failed:
                app_server.run_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(app_server.run_dir / "failure.png"), full_page=True)
                except Exception:  # pragma: no cover - best-effort diagnostics
                    pass
                try:
                    shutil.copyfile(app_server.log_path, app_server.run_dir / "server-failure.log")
                except OSError:  # pragma: no cover - best-effort diagnostics
                    pass
            context.close()
            browser.close()
    finally:
        playwright.stop()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
