# AGENTS.md — DatasetPeek

This file provides guidance for coding agents (e.g., Codex) working on this repository.

The goal is to keep instructions minimal, explicit, and actionable.

---

## Project Overview

DatasetPeek is a **fast, minimal profiler for CSV and Parquet files**, from local uploads or S3-compatible object storage.

Core idea:
- Analyze a local file or S3-compatible object
- Return a **quick, high-signal overview** and portable reports
- No heavy EDA, no complex UI

This is a **server-rendered app**, not a frontend-heavy application.

---

## Tech Stack

- Backend: Python + Robyn
- Data processing: Polars
- Templating: Jinja2
- Frontend: server-rendered Jinja, minimal CSS, and small amounts of vanilla JavaScript (no framework)

---

## Architecture

- `routes/` → HTTP endpoints (Robyn)
- `services/` → core logic (profiling, heuristics, file reading)
- `templates/` → Jinja templates
- `static/` → browser assets such as CSS and JavaScript
- `app/services/profile_model.py` → structured profile model shared by the UI and reports

Separation of concerns:
- routes = orchestration
- services = logic
- templates = rendering

---

## Core Principles

When modifying or adding code, always follow:

1. **Keep it minimal**
   - Do not add unnecessary features
   - Avoid abstractions unless clearly needed

2. **Optimize for speed**
   - Avoid heavy computations
   - Do not compute full distributions

3. **Signal over completeness**
   - Prefer useful heuristics over exhaustive analysis

4. **Single-page UX**
   - Do not introduce multi-page flows or complex navigation

---

## Data Handling

- Use **Polars** for all data operations
- Avoid pandas unless strictly necessary
- Prefer vectorized operations

Sampling:
- Preserve configured preview sizes and the deterministic sample seeds in
  `app/services/profiler.py`; do not hard-code a separate sampling policy.

---

## Heuristics (Important)

Implemented in `services/heuristics.py`.

Must include:
- low variance (top value ≥ 95%)
- binary / potential target
- missingness
- categorical detection
- ID detection

Do not add complex statistical methods.

---

## UI Guidelines

- Use Jinja templates only
- No frontend frameworks
- Keep the single-page results layout focused on summary, signals, columns,
  numeric summary, previews, and report downloads.

Tables:
- truncate long text
- no sorting/filtering/pagination

---

## File Handling

- Accept:
  - CSV
  - Parquet
- Sources:
  - local file upload
  - S3-compatible object URI, including configured private endpoints

CSV assumptions:
- header present
- delimiter auto or comma fallback

Reject unsupported formats with clear error.

---

## What NOT to Do

- Do NOT add:
  - charts
  - correlations
  - dashboards
  - authentication
  - persistence
  - new server API routes without an approved product requirement

- Do NOT turn this into a full EDA tool

---

## Code Style

- Keep functions small and focused
- Prefer readability over cleverness
- Avoid deep nesting
- Use clear variable names

---

## Testing (Lightweight)

Before finishing a task:

- Run `make check` (Ruff lint/format, mypy, pytest).
- Run `make coverage` for line and branch coverage without a fail-under gate.
- Run `make audit` for dependency changes; network is required.
- Use uv 0.11.19 and `uv sync --locked --group dev`.
- The default suite excludes the `browser` marker. For browser/client-side
  changes, install the optional browser group and Chromium, then run
  `make browser-test`; do not make Playwright a runtime dependency.

  ```bash
  uv sync --locked --group dev --group browser
  uv run --locked --group browser playwright install chromium
  make browser-test
  ```

- Follow [CONTRIBUTING.md](CONTRIBUTING.md): branch from `dev`, PR into `dev`;
  the maintainer releases through same-repository `dev` → `master`.

- Ensure app runs locally
- Test with:
  - small CSV
  - small Parquet
- For relevant changes, cover S3-compatible reads and Markdown/HTML report output.
- Verify:
  - summary renders
  - sample renders
  - no crashes

---

## Maintainer Release Checklist

This repository uses `master` as the production branch; there is no `main`
branch. Follow the full flow in [CONTRIBUTING.md](CONTRIBUTING.md):

1. Merge feature and fix PRs into `dev` after required checks pass.
2. Prepare the version, lockfile, changelog, README, PRD, and versioned examples
   on a short-lived release branch from current `dev`, then merge its PR into
   `dev`.
3. Open the same-repository release PR from `dev` to `master`. Merge it with a
   merge commit after the combined diff and required checks pass; never squash
   or rebase the long-lived branches.
4. Tag the verified `master` release merge as `vX.Y.Z` and publish the release
   notes. Verify deployment separately when applicable.
5. Synchronize `master` back into `dev` through a fresh
   `chore/sync-release-*` branch and PR, merging that PR with a merge commit.
6. Close superseded or incorrectly based release PRs and remove merged
   short-lived remote branches. Do not close unrelated Dependabot or security
   PRs as general cleanup.

Do not push directly to protected `dev` or `master`, delete either long-lived
branch, or treat a merged PR as proof that a deployment completed.

---

## Execution Strategy for Agents

When implementing features:

1. Start from existing structure
2. Modify only necessary files
3. Keep changes minimal
4. Validate end-to-end (upload → render)

If unsure:
- prefer simpler implementation
- avoid over-engineering

---

## Skills and Efficient Routing

Use skills when their stated conditions match the task. Load the applicable
skill before acting, and follow its workflow and approval gates.

### Route by task

- **New feature, subsystem, or architectural change:** start with `brainstorming`;
  wait for the required design approval, then use `writing-plans` before
  implementation.
- **Bug or unexpected behavior:** start with `systematic-debugging`; establish
  the cause before changing code.
- **Code changes:** use `testing` for behavior-focused tests and
  `verification-before-completion` before claiming the work is done.
- **Documentation:** use `documentation` when creating or updating project docs.
- **Library, framework, SDK, API, CLI, or cloud-service questions:** use
  `context7` for current official documentation where available.
- **Other specialized work:** choose the skill whose description directly
  matches the task (for example, Azure, Python, CI/CD, or browser automation).

Use `using-superpowers` at the start of a conversation when available. Do not
load unrelated skills or stack multiple process skills that prescribe the same
step; follow the more specific workflow and include only relevant supporting
skills.

### Keep work efficient and cost-conscious

- Choose the smallest sufficient approach: inspect only relevant files, make
  the narrowest change, and run targeted checks before broader validation.
- Avoid external research for stable, repository-local questions. Use current
  documentation when an external API or version-specific behavior matters.
- Do not delegate or parallelize routine, tightly coupled, or very small work.
  Use agents or parallel calls only when tasks are genuinely independent and
  the expected time or quality benefit outweighs coordination cost.
- Prefer the least expensive model and tools that can reliably complete the
  task; escalate only when complexity or uncertainty warrants it.
- Never skip a required skill, approval gate, security check, or verification
  step merely to save time or tokens.

---

## Final Rule

This project is intentionally **small and focused**.

If a change makes it:
- heavier
- slower
- more complex

→ do not implement it.
