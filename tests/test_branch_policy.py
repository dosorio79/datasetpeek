"""Exercise the exact metadata-only policy embedded in CI without GitHub access."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("base", "head", "repository", "allowed"),
    [
        ("dev", "feature/example", "dosorio79/datasetpeek", True),
        ("dev", "feature/example", "contributor/fork", True),
        ("dev", "dependabot/uv/example", "dosorio79/datasetpeek", True),
        ("master", "dev", "dosorio79/datasetpeek", True),
        ("master", "feature/example", "dosorio79/datasetpeek", False),
        ("master", "dev", "contributor/fork", False),
        ("dev", "master", "dosorio79/datasetpeek", False),
        ("dev", "main", "contributor/fork", False),
        ("dev", "dev", "contributor/fork", False),
        ("dev", "feature/$(exit 99)", "contributor/fork", True),
        ("unexpected", "feature/example", "contributor/fork", False),
    ],
)
def test_pr_branch_policy(tmp_path, base, head, repository, allowed):
    event = {
        "pull_request": {
            "base": {"ref": base},
            "head": {"ref": head, "repo": {"full_name": repository}},
        }
    }
    result = run_policy(tmp_path, "pull_request", event)
    assert (result.returncode == 0) is allowed, result.stderr


@pytest.mark.parametrize("event_name", ["push", "schedule", "workflow_dispatch"])
def test_non_pr_events_pass(tmp_path, event_name):
    assert run_policy(tmp_path, event_name, {}).returncode == 0


def test_missing_pr_metadata_fails_closed(tmp_path):
    assert run_policy(tmp_path, "pull_request", {}).returncode != 0


def run_policy(tmp_path, event_name, event):
    workflow = Path(".github/workflows/ci.yml").read_text()
    # Test the inline Python, not a second implementation of the policy.
    script = textwrap.dedent(
        workflow.split("# BEGIN BRANCH POLICY\n", 1)[1].split("# END BRANCH POLICY", 1)[0]
    )
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    return subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "GITHUB_EVENT_NAME": event_name, "GITHUB_EVENT_PATH": str(event_path)},
        capture_output=True,
        text=True,
        check=False,
    )
