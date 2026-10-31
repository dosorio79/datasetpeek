# Contributing to DatasetPeek

Start work from `dev` and submit a pull request back into `dev`. The maintainer
reviews and merges contributions, then opens a release PR from `dev` into
`master`. This repository uses `master` as its main/release branch, not `main`.

**Rollout status:** Quality tooling and CI configuration are implemented locally.
The new checks and branch protections are not active on GitHub until published,
verified, and applied. See the [quality and security plan](docs/superpowers/plans/2026-10-31-repository-quality-security.md)
and [protection rollout](docs/branch-protection-plan.md).

## Set up your checkout

Use Python 3.12 and uv. Use uv **0.11.19**, matching CI (the audit command is experimental).
For fork contributions, fork the repository on GitHub, clone your fork, and
add the upstream repository once:

```bash
git remote add upstream https://github.com/dosorio79/datasetpeek.git
git fetch upstream
git switch -c feature/short-description upstream/dev
uv sync --locked --group dev
```

Here `origin` is your fork and `upstream` is the maintained repository.
If you already have a checkout, inspect `git status` and `git remote -v`
first; preserve any uncommitted work. Use a new descriptive branch for each PR.

If the maintainer has explicitly granted upstream write access, clone the
maintained repository and use `origin/dev` instead of `upstream/dev` above.
Still push only your feature branch; do not push directly to `dev` or `master`.
Use `fix/` or `docs/` prefixes for fixes or documentation work.

## Develop and check

Keep changes focused and preserve the small Robyn/Polars/Jinja architecture.
Use synthetic fixtures; never commit real user datasets, credentials, `.env`
files, Terraform state, or tokens. Read [agents.md](agents.md) for project
conventions, including when using a coding agent.

Run the local checks that mirror CI; the browser journey is separate:

```bash
uv sync --locked --group dev
make check  # Ruff lint/format check, mypy, pytest
make coverage  # branch coverage; no fail-under threshold
make audit  # dependency compatibility and network-backed vulnerability audit
uv run --locked python main.py
```

Without make, run:

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app main.py
uv run --locked pytest -q
uv run --locked coverage run -m pytest -q
uv run --locked coverage report -m
uv pip check --python .venv/bin/python
uv audit --locked --python-version 3.12 --python-platform linux
```

Coverage measures line and branch execution for `app` and root `main.py`. It
does not execute browser JavaScript or the inline workflow policy, and the
combined number is not line coverage. There is no percentage gate; use the
missing-line and partial-branch report to target meaningful gaps.

The default suite excludes the `browser` marker and must collect without
optional Playwright packages. The Chromium journey is optional and noticeably
slower than `make check`; it downloads a browser during first-time setup. To
run the one real Chromium upload, sample cycling, and download journey, install
the browser group and Chromium once:

```bash
uv sync --locked --group dev --group browser
uv run --locked --group browser playwright install chromium
make browser-test
```

On Windows without make, run
`uv run --locked --group browser pytest tests/browser -m browser -q`. CI installs
Chromium with OS dependencies in the separate `browser-smoke` job. Local browser
success does not prove the hosted check passes, and that job is not one of the
four prepared required branch-protection checks. Browser tests bind to loopback,
own their server process, and use synthetic data and settings.

For Windows, the environment interpreter is `.venv/Scripts/python.exe`.
For a custom `UV_PROJECT_ENVIRONMENT`, point `uv pip check --python` at that
environment's interpreter. The audit targets the supported CI environment:
Python 3.12/Linux, with runtime and development dependencies.

Use `uv run --locked ruff format .` to apply formatting. Editor Ruff/mypy
integration is optional; CI remains the shared verification gate. No mandatory
hooks. For relevant UI changes, try a small CSV and Parquet upload and inspect
reports. S3 changes must retain mocked coverage; production credentials are
unnecessary. Audit service outages fail the check; rerun after recovery rather
than disabling the check or ignoring findings.

## Open your PR into dev

1. Update your feature branch when needed: fetch upstream, then merge
   `upstream/dev` into your feature branch (use `origin/dev` for a shared-repo
   checkout). Resolve conflicts and rerun relevant checks. Avoid rewriting
   shared history or force-pushing protected branches.
2. Commit the focused change and push your branch:
   `git push -u origin feature/short-description`.
3. On GitHub select **base repository `dosorio79/datasetpeek`, base `dev`**,
   and your feature branch as the head. GitHub may otherwise default to `master`.
4. Describe the problem, change, tests run, and any relevant limitations.
   Request review from `dosorio79`; respond to feedback and resolve discussions.
5. Leave merging to the maintainer. Feature PRs may be squash-merged. Start
   subsequent work from fresh upstream `dev`, not the previously merged branch.

The configured required checks are `test`, `quality`, `dependency-audit`, and
`branch-policy`. The last check prevents accidental release PRs from feature
branches; it is not a substitute for repository access controls. The separate
`browser-smoke` job is intended to be visible CI evidence, not a fifth required
context; adding it to branch protection would be a separate rollout decision.

## Maintainer release flow

After reviewing and merging feature PRs into `dev`, the maintainer opens
**same-repository `dev` → `master`**, checks the combined diff and CI, and
merges using a **merge commit**. Preserve ancestry rather than squashing or
rebasing the long-lived release branch. Keep `dev`; do not delete it after release.

After every release, synchronize the release merge commit back into `dev`.
With a clean maintainer checkout (`origin` is the maintained repository):

```bash
git fetch origin
git switch -c chore/sync-release origin/dev
git merge origin/master
git push -u origin chore/sync-release
```

Open `chore/sync-release` → `dev`, then **merge with a merge commit**, not squash
or rebase. Use a fresh sync branch name each time. This preserves `master`'s
ancestry so the next release can satisfy strict up-to-date checks. Direct
`master` → `dev` PRs are intentionally rejected by branch policy. This sync PR
is the exception to the usual squash preference for short-lived branches.

Version/changelog updates belong on a short-lived branch from `dev`, through
a PR into `dev`, before the release PR. Verify any Render deployment separately;
a merged PR does not prove deployment succeeded. No rename to `main` is planned.

Dependabot version updates will target `dev`. GitHub security updates target
`master` regardless of that setting: the maintainer reproduces the fix on a
branch from `dev`, reviews it via a PR into `dev`, then releases normally. Link
the original bot PR and close it once the released fix resolves the alert.
Do not bypass the release flow to merge a bot PR directly into `master`.

## Access and sensitive reports

Fork contributions without upstream write access keep merging under the
maintainer's control. If upstream write access is granted, the zero-approval
policy does not technically prevent a collaborator merging an eligible PR;
leaving merges to the maintainer is then an explicit trust agreement. The
maintainer must settle access restrictions before inviting a writer.

Do not post vulnerabilities containing secrets or private data in public
issues. See [SECURITY.md](SECURITY.md) for current reporting status; arrange a private
channel with the maintainer before sending sensitive details.
