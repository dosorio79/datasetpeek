# Repository Quality and Security — Design Spec

**Status:** Implemented locally; remote activation pending (see implementation progress)
**Date:** 2026-10-31
**Scope:** Lightweight safeguards before inviting a collaborator

## Intent and current state

Catch common mistakes, vulnerable dependencies, and accidental secret exposure
without turning a small project into a compliance platform. Keep local checks
easy to reproduce and dependency-update noise low.

Before implementation, inspection found Python 3.12 CI running only pytest, a committed `uv.lock`, and
three runtime dependencies (Jinja2, Polars, Robyn). There was no Ruff, mypy,
dependency audit, or Dependabot configuration. Some service code is typed;
Robyn route inputs are dynamic. Terraform manages branch protection:
`master` requires `test` and a PR, with zero approvals; `dev` allows direct
pushes. These are repository configuration findings, not a live settings audit.

## Approaches and recommendation

1. Tests plus dependency updates only: minimal work, but misses the requested
   lint/type checks and offers little feedback to a new contributor.
2. **Recommended:** a small local quality gate, one dependency audit, weekly
   updates, built-in GitHub security, and protected integration branches.
3. Strict typing everywhere, multiple security scanners, coverage thresholds,
   and mandatory hooks: more maintenance and adoption churn than justified now.

Option 2 was authorized for implementation. Assumptions:
one occasional trusted collaborator, no paid security services, and continued
Python 3.12/Linux CI. Inviting someone does not imply changing repo visibility.

## Quality checks

- Add Ruff and mypy to the locked dev dependency group. Keep runtime
  dependencies unchanged. Select compatible releases during implementation.
- Ruff checks all tracked Python code with explicit rules `E4`, `E7`, `E9`,
  `F`, `I`, `B`, and `UP`; target Python 3.12 and use line length 100.
  Use Ruff formatting as the single formatter. No preview rules or `ALL`.
- Mypy checks `app/` and root `main.py`, with Python 3.12,
  `check_untyped_defs`, `warn_unused_ignores`, `warn_redundant_casts`, and
  `no_implicit_optional` enabled. Tests remain covered by Ruff and pytest.
  Do not enable global strict mode yet. Add useful annotations at boundaries;
  do not redesign working routes to satisfy typing.
- Missing third-party typing may receive a narrowly scoped module override
  with a reason. No global missing-import suppression or wholesale app exclusion.
- Keep the full existing pytest suite. Add behavior regression tests when a
  lint/type fix actually changes behavior. No arbitrary coverage percentage.
- One deliberate formatting pass is acceptable; keep it reviewable separately
  from functional fixes. Do not upgrade unrelated runtime packages.

## Dependency health and update policy

- `uv pip check` checks installed dependency compatibility. It does not check
  vulnerabilities; `uv audit` supplies that separate check.
- Audit the locked runtime and dev dependency set, including transitives, on
  Python 3.12/Linux using
  `uv audit --locked --python-version 3.12 --python-platform linux`.
  uv audits all dependency groups by default. Pin uv 0.11.19 (confirmed locally
  to support this command) in CI and document it for contributors. Verify real
  audit results and nonzero failure behavior during implementation; availability
  alone is not an audit pass. No pip-audit dependency or requirements export.
- Known vulnerabilities fail the audit, including those with no fix. Any
  accepted advisory needs its exact ID, justification, owner, and review date
  recorded beside the audit configuration. No blanket severity suppression,
  automatic fixes, or `continue-on-error`. Network/service errors are reported
  as failed audits, not clean results; rerun after transient outages.
- Configure Dependabot `uv` and `github-actions` ecosystems at `/`, weekly,
  with `target-branch: dev`. Group minor/patch updates per ecosystem;
  leave majors separate; cap open version-update PRs at three per ecosystem.
  No automatic merge. Security fixes should be reviewed promptly.
- Keep config on the default branch so scheduled automation can activate.
  Enable dependency alerts/security updates where supported, but retain the
  explicit audit rather than assuming GitHub covers every locked dependency.
- Version-update PRs target `dev`. GitHub security-update PRs still target
  default branch `master`; the owner recreates the fix on a branch from `dev`,
  opens a PR into `dev`, and releases through `dev` → `master`. Link and close
  the original bot PR after the release resolves the alert. Do not merge it
  directly or assume `target-branch` redirects security updates.

## CI design and supply-chain hygiene

- Preserve the required job name `test`; add jobs named `quality` and
  `dependency-audit`. These jobs use Python 3.12 and a locked dev sync.
  Add a fourth, lightweight required job `branch-policy` that reads PR metadata
  without checking out or executing contributor code. For PRs into `master`,
  require head branch `dev` AND head repository `dosorio79/datasetpeek`. For
  PRs into `dev`, reject head names `dev`, `master`, and `main`; allow other
  names (including bot branches and fork feature branches). On non-PR events,
  pass explicitly. Use structured event data, never shell-interpolate PR input.
- Run all four on PRs targeting `dev` or `master`, pushes to those branches,
  weekly schedule, and manual dispatch. No path filters on required checks.
  One workflow is sufficient; the small weekly test rerun is acceptable.
- `quality`: Ruff lint, Ruff format check, then mypy. `test`: pytest.
  `dependency-audit`: installed-package compatibility and locked audit.
- Use read-only `contents` permission, ten-minute job timeouts, and cancel
  superseded runs using workflow/event/ref-specific concurrency groups.
- Pin third-party actions to verified full commit SHAs with release comments;
  Dependabot maintains them. Use one explicit uv version across jobs and
  document it locally. No deployment credentials or other secrets in checks.
- Use `pull_request`, never privileged `pull_request_target` to execute PR
  code. Contributor and bot PRs must work without repository secrets.
- These checks verify the supported CI environment, not every platform in the
  universal lock, malicious-package behavior, or all application vulnerabilities.

## Collaboration and GitHub security

- Extend existing Terraform protection for both `master` and `dev`: require
  PRs, up-to-date branches, and `test`, `quality`, `dependency-audit`, `branch-policy`; disallow
  force pushes and deletion; retain admin enforcement on `master` and enable
  it on `dev`. Require conversation resolution on both.
- Branch flow: start `feature/*`, `fix/*`, or `docs/*` from updated `dev`;
  open a PR into `dev`; the owner reviews and merges. Only the owner opens
  and merges release PRs from this repository's `dev` into `master` (the main
  branch; no branch rename is planned). Use merge commits for release PRs to
  preserve ancestry; squash is suitable for short-lived feature PRs.
  After each release, merge `master` into a short-lived sync branch from `dev`
  and PR that branch into `dev`, using a merge commit (never squash/rebase).
  This propagates release ancestry for strict up-to-date checks without a
  direct `master` → `dev` PR, which branch policy rejects.
- For enforceable owner-only merging with minimum administration, prefer fork
  contributions without upstream write access where visibility permits. Keep
  zero required approvals so the owner can release without a second reviewer.
  Fork contributors cannot merge upstream; the owner reviews their changes.
- If granting upstream write access, owner-only merging is a convention, not
  enforced by zero approvals or the branch-policy job. A writer can merge green
  PRs, including release PRs, and propose workflow edits. Before granting access,
  explicitly decide whether that trust is acceptable; otherwise inspect available
  ruleset/actor restrictions or use fork-only access. Do not claim branch naming,
  PR authorship, or a contributor-editable workflow is an authorization boundary.
  Do not silently grant write access or purchase an organization plan.
- Keep deployment credentials and settings with the owner. A release merge is
  not evidence of deployment; verify Render separately when releasing.
- Inspect repository visibility, entitlement, and existing settings first.
  Enable free built-in secret scanning/push protection, private vulnerability
  reporting, and CodeQL default setup where available. Use its default query
  suite; inspect the first successful analysis and actual branch coverage.
  Initially triage CodeQL findings without adding another required check.
  Do not purchase a plan or change visibility to enable these features.
- Add short `CONTRIBUTING.md`, `SECURITY.md`, and a PR template: local commands,
  feature-branch-to-dev flow, release flow, dependency update flow, regression
  expectations, and private security reporting. Never submit credentials or
  user datasets in issues, logs, screenshots, or fixtures.
- Extend `.gitignore` for `.env`/`.env.*` (retain `.env.example`) and mypy/Ruff
  caches; preserve existing Terraform ignores. Ignore patterns do not remove
  already tracked secrets. If an exposure is found, stop copying it and arrange
  rotation; history rewriting is outside this plan.

## Rollout and non-goals

Land workflow/configuration and fix the initial baseline before activating new
required checks. Observe the exact successful check names on both branch flows
before applying Terraform. Remote settings changes, collaborator invitations,
Terraform apply, commits, PR creation, releases, and deployment are separate
authorized actions. Local implementation is complete; publication and remote
activation remain pending. See the linked plan and progress log.

No new product features, auth, infrastructure migration, paid scanning,
mandatory pre-commit installation, Bandit/Semgrep alongside CodeQL, SBOM/signing
pipeline, browser test suite, or Python/OS test matrix. Do not mix in the 0.5.0
version bump or claim that scans make the application secure.

## Acceptance criteria

1. A fresh locked dev install reproduces lint, format, typing, tests,
   dependency compatibility, and vulnerability checks locally.
2. Ordinary and Dependabot PRs run secretless checks; a deliberate lint/type
   failure blocks its job, and an advisory/service failure fails the audit.
3. Weekly updates maintain `uv.lock` and action pins without duplicate pip
   update streams; scheduled scans activate after default-branch merge.
4. Live branch rules require the four observed job names only after they
   exist; contributor guidance accurately states the approval policy.
5. GitHub security activation and first scan results are recorded separately
   from local verification, including unavailable features and branch gaps.
6. A feature → `master` PR and a fork `dev` → `master` PR fail branch policy;
   same-repository `dev` → `master` and feature → `dev` PRs pass.
7. Existing upload, S3, profiling, and report tests still pass; application
   behavior and runtime dependencies are unchanged except justified fixes.

## Official references checked during planning

- [uv and Dependabot](https://docs.astral.sh/uv/guides/integration/dependabot/)
- [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- [Ruff rules](https://docs.astral.sh/ruff/rules/)
- [Gradual mypy adoption](https://mypy.readthedocs.io/en/stable/existing_code.html)
- [uv audit](https://docs.astral.sh/uv/reference/cli/#uv-audit)
- [Dependabot PR targets](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/customizing-dependabot-prs)
- [Personal repository permissions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository)
- [GitHub repository security](https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository)
