# Repository quality/security implementation progress

Plan: [2026-10-31-repository-quality-security.md](2026-10-31-repository-quality-security.md)

- User authorized implementation; local changes only, no commit or remote activation.
- Baseline: `uv run --locked pytest -q` → 72 passed.
- Existing documentation changes preserved. Work stays on `dev`; no isolation
  benefit warrants moving the user's uncommitted planning documents.
- Tasks 1–3 share local commands and CI names; task 4 must wait for published
  successful checks before applying protection. No interface conflict found.

## Task 1 — complete

- Added locked Ruff 0.17.3 and mypy 2.4.1. All pre-existing locked package
  versions are preserved; uv upgraded lock metadata from revision 1 to 3.
- Initial diagnostics: 38 lint findings and five mypy errors. Safe Ruff fixes,
  formatting, one unused calculation removal, and three annotation corrections
  established the baseline; no broad typing suppressions or behavior redesign.
- Ruling: Ruff 0.17 can process Markdown code blocks; limited its include paths
  to Python/pyi/pyproject files and reverted its incidental old-plan formatting.
- Ruling: sandbox cache/network/socket restrictions required a temporary uv cache
  and escalated verification; no application change was made to hide those errors.
- Fresh `/tmp/datapeek-quality-venv`, Python 3.12.10, uv 0.11.19:
  `make check audit` passed: Ruff lint/format (21 files), mypy (14 source files),
  87 tests, installed compatibility (28 packages), audit (29 packages, no known
  vulnerabilities or adverse statuses). Universal lock has 30 entries including
  the local project and platform/version-dependent packages.

## Task 2 — local implementation complete; hosted checks pending

- Four stable jobs, read-only token, no checkout in branch-policy, no persisted
  checkout credentials, full upstream action SHA pins, pinned uv, bounded runs.
- Added 15 policy tests: observed all failing before implementation, then passing.
  Includes fork/bot paths, release provenance, malformed metadata, non-PR events,
  and branch text containing shell syntax (never interpolated).
- Ruff/mypy deliberately reject temporary bad code; stale lock probe fails
  `uv sync --locked`. Restricted-network audit exited 2 on lookup failure.
- Disposable Jinja2 3.1.5 lock (never installed) produced audit exit 1 with
  GHSA-cpwx-vrp4-4pq7 / PYSEC-2026-1471. Project audit exited 0.
- Verified upstream action refs through GitHub; actionlint 1.7.12, downloaded
  from its official release and checksum-verified, validated the workflow.
- Dependabot YAML reviewed: uv + Actions, weekly, dev target, minor/patch groups,
  three open PRs each. No hosted workflow/Dependabot execution claimed.

## Task 3 — complete

- Contributor guide, README, agent guidance, Makefile, PR template, SECURITY.md
  now describe implemented commands and distinguish pending remote activation.
- Private reporting is disabled, so no fictional reporting address is advertised.

## Task 4 — local preparation complete; remote activation pending

- Both Terraform branch resources prepared for four checks, PRs, conversation
  resolution, admin enforcement, no deletion/force push, zero approvals.
- `terraform fmt -check` and `terraform validate` passed using existing provider
  6.12.1. Live read-only plan failed HTTP 401 Bad credentials using the existing
  local Terraform variables; no credential values were printed or changed.
- GitHub read-only inspection: public repo; merge commits allowed; secret
  scanning/push protection enabled; private reporting disabled; Dependabot
  security updates disabled; CodeQL default setup not configured.
- No remote settings changed, no collaborator invited, no commits, no PRs,
  no deployment. New required checks must first be published and observed on
  both PR base branches; only then review/apply Terraform with valid credentials.
- Owner-only merging relies on fork-only upstream access; upstream write access
  is a trust decision, not constrained by this zero-approval workflow.

## Final review and handoff

- Independent review found one material documentation omission: strict checks
  require the release merge commit to be synchronized back into `dev`.
  Fixed contributor guide, spec, plan, and protection documentation to use a
  short-lived sync branch and a merge-commit PR (not squash/rebase). No policy
  code change was needed; ordinary short-lived branch → dev is already tested.
- Stale-lock verification repeated online after an offline-cache failure:
  `uv sync --locked` explicitly rejected changed project metadata because the
  lockfile needed updating. Temporary probe files were outside the repository.
- No deferred review findings. Local implementation is ready for review;
  remaining work is publication, hosted CI evidence, valid Terraform credentials,
  and separately authorized GitHub activation in the documented order.
