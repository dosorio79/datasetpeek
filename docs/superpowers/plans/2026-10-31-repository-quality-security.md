# Repository Quality and Security Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans when implementation
> is authorized. Keep this tightly coupled work in the primary agent.

**Status:** Implemented locally and verified; publication and remote activation pending.
**Evidence:** [Progress and verification](2026-10-31-repository-quality-security-progress.md).
**Goal:** Give an occasional collaborator fast feedback and practical security checks.
**Architecture:** Extend uv/pytest CI and existing Terraform branch rules.
Use GitHub's built-in security features rather than adding overlapping scanners.
**Tech stack:** Python 3.12, uv, Ruff, mypy, pytest, uv audit, GitHub Actions,
Dependabot, existing GitHub Terraform provider.
**Spec:** [Repository Quality and Security](../specs/2026-10-31-repository-quality-security-design.md)

## Global constraints

- Preserve application behavior, runtime dependencies, and existing JSON export work.
- Required checks: `test`, `quality`, `dependency-audit`, `branch-policy`; Python 3.12/Linux only.
- Owner reviews and merges; prefer fork-only access to enforce owner control.
  Zero required approvals; upstream write access weakens that control.
- No remote mutations or commits without authorization; no secrets in CI.
- Implement baseline fixes before requiring checks; no suppression to manufacture green CI.

## Review focus

- Fork and bot PRs must pass without secrets or write tokens (task 2).
- Lockfile drift and advisory outages must fail clearly (tasks 1–2).
- Dynamic Robyn/Polars boundaries must retain behavior after typing fixes (task 1).
- Default-branch scheduling and dependency PR targets must actually activate (tasks 2–4).
- New required contexts must not deadlock merges or require an absent reviewer (task 4).

## Task 1: Establish a reproducible local baseline

**Files:** Modify `pyproject.toml`, `uv.lock`, `.gitignore`; narrowly fix
`main.py`, `app/**/*.py`, and `tests/**/*.py` only where diagnostics require it.
**Produces:** Locked tool versions and clean local commands consumed by CI.

- [x] Record clean/dirty Git state and run existing `uv run pytest -q` before edits.
- [x] Add Ruff and mypy to dev dependencies using uv; inspect lock diff
  for unintended runtime upgrades. Use uv 0.11.19 in CI and docs; verify its audit behavior.
- [x] Configure Ruff and mypy exactly as specified; run diagnostics before fixes.
- [x] Apply a reviewable formatting/import pass, then minimal lint/type repairs.
  Justify narrow typing exceptions; preserve route injection and return behavior.
- [x] Add regression tests only for behavioral fixes; run existing route, S3,
  CSV, settings, and JSON export tests after repairs. Do not create tests that
  simply assert the content of tooling configuration.
- [x] Add local secret/cache ignore patterns without touching tracked user files.
- [x] Verify these commands exit zero in a fresh temporary environment using
  `UV_PROJECT_ENVIRONMENT` outside the working environment:

```bash
export UV_PROJECT_ENVIRONMENT="$(mktemp -d /tmp/datasetpeek-checks.XXXXXX)/venv"
uv sync --locked --group dev
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app main.py
uv run --locked pytest -q
uv pip check --python "$UV_PROJECT_ENVIRONMENT/bin/python"
uv audit --locked --python-version 3.12 --python-platform linux
```

Confirm runtime/dev transitives are audited and environment markers are handled
for the supported runner. No requirements export or pip-audit installation.
If an audit reports an advisory, investigate and propose the smallest fix or
explicit documented exception; do not silently waive it. Audit requires network.

## Task 2: Wire quality checks, dependency audit, and updates into CI

**Files:** Modify `.github/workflows/ci.yml`; create `.github/dependabot.yml`
and `tests/test_branch_policy.py` to execute the exact inline policy against events.
**Consumes:** Task 1 commands, tool versions, and clean baseline.
**Produces:** Four stable checks and weekly default-branch update automation.

- [x] Add the four jobs, event/branch selection, weekly/manual triggers,
  read-only permissions, ten-minute timeouts, and cancellation policy from spec.
  Use the native locked uv audit command. Point
  `uv pip check --python` explicitly at the synced environment's interpreter.
- [x] Pin actions to verified upstream SHAs with version comments. Pin the
  tested uv version identically in each job. Retain locked dependency installs.
- [x] Configure weekly `uv` and `github-actions` version updates to `dev`, with
  minor/patch groups and three open version-update PRs per ecosystem.
- [x] Implement metadata-only `branch-policy` per spec, without checkout. Test
  event fixtures for feature → dev (same repo/fork), bot → dev, same-repo dev →
  master, feature → master, fork dev → master, master → dev, and push/schedule.
  Only the intended paths pass; adversarial branch text must stay inert.
- [x] Validate YAML and review event coverage, permissions, pins, and job names.
  Locally exercise a temporary unused import and incompatible annotated value;
  prove Ruff/mypy return nonzero, then remove the probes and rerun clean checks.
- [x] In a disposable copy, demonstrate stale project/lock metadata fails the
  locked install. Exercise audit failure using a disposable uv project/lock
  containing a known vulnerable registry dependency; never sync or install it.
  Confirm network failure also cannot become a passing audit.
- [ ] After separately authorized publication, inspect all four jobs on an
  actual PR and verify fork/bot permission assumptions. Record pending live
  evidence honestly if no suitable PR exists. No test fixtures containing secrets.

## Task 3: Document contributor and security workflows

**Files:** Finalize existing draft `CONTRIBUTING.md`; create `SECURITY.md`,
`.github/pull_request_template.md`; modify `README.md`, `agents.md`, and `Makefile`.
**Produces:** One short contributor path with matching local and CI commands.

- [x] Document setup, tested uv version, task 1 commands, and optional editor
  integration; no mandatory hooks or extra command framework.
- [x] Finalize guide for feature branches from `dev`, PRs into `dev`, and
  owner-managed release PRs `dev` → `master` with merge commits. Version-update
  PRs target `dev`; recreate default-branch security fixes through `dev` before
  release. Document fork setup and the upstream-write permission tradeoff.
  After releases, use a sync branch from `dev` that merges `master`, then a
  merge-commit PR back into `dev`; do not squash away the release ancestry.
- [x] Add a brief PR checklist for purpose, verification, and relevant security
  impact; document synthetic fixtures and prohibition on sharing secrets/data.
- [x] Document private vulnerability reporting only after confirming an actual
  private channel exists. Until activation, explicitly state that the channel
  is pending; do not invent an email address or invite sensitive public issues.
- [x] Extend existing `make check` to lint, format-check, type-check, and test;
  add `make audit` for compatibility plus native vulnerability audit (network).
  Keep direct uv commands available; do not hide network checks in `make check`.
- [x] Link guidance from README and update agent verification commands; check
  links and ensure commands exactly match CI. No unrelated release metadata edits.

## Task 4: Prepare protection changes, then activate remotely when authorized

**Files:** Modify `infra/github/main.tf` and `docs/branch-protection-plan.md`.
**Consumes:** Configured CI names for preparation; observed successful runs on
both branch flows are required before remote apply.
**Produces:** Reviewed Terraform changes plus a separate activation record.

- [x] Extend both branch rules as specified: four required checks, up-to-date
  PRs, no force pushes/deletion, admin enforcement, conversation resolution,
  zero required approvals. Check compatibility with the locked provider schema.
- [x] Update branch documentation to explain occasional collaboration, the
  fork-only owner control and the trust implications of upstream write access.
  Inspect actual access/visibility before any invitation; no invitation in scope.
- [ ] Complete live planning: `terraform fmt -check` and `terraform validate` passed;
  the read-only live plan failed with HTTP 401 from existing local credentials.
  Refresh credentials privately before retrying. Run validation after provider init
  if needed. Prepare a read-only plan with existing authorized credentials;
  keep sensitive plan/state files ignored and avoid printing secret values.
  If access is unavailable, record validation versus live-plan gaps separately.
- [ ] Before apply, confirm new workflows have landed and successful job names
  are visible on both branch flows. Do not require checks that cannot run yet.
- [ ] With separate remote authorization, apply the reviewed Terraform plan,
  verify both branch protections, and confirm a subsequent plan shows no drift.
- [ ] Inspect live GitHub security settings/entitlement. Enable available free
  dependency alerts/security updates, secret scanning/push protection, private
  reporting, and CodeQL default setup. Do not duplicate an existing CodeQL setup.
- [ ] Inspect the first successful CodeQL analysis, branch coverage, Dependabot
  configuration processing, and scheduled workflow availability on `master`.
  Record unsupported features and pending bot/scheduled runs without claiming
  activation from configuration alone. Update SECURITY.md with verified channel.

## Completion evidence

Record local check results, initial diagnostics and exceptions, successful CI
run links, actual branch settings, activated security features, and remaining
live-verification gaps. No production deployment is necessary for these controls.
Do not claim this is an application penetration test or a guarantee of security.
