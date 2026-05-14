# AGENTS.md — DatasetPeek

This file provides guidance for coding agents (e.g., Codex) working on this repository.

The goal is to keep instructions minimal, explicit, and actionable.

---

## Project Overview

DatasetPeek is a **fast, minimal profiler for CSV and Parquet files**.

Core idea:
- Upload a file
- Return a **quick, high-signal overview**
- No heavy EDA, no complex UI

This is a **server-rendered app**, not a frontend-heavy application.

---

## Tech Stack

- Backend: Python + Robyn
- Data processing: Polars
- Templating: Jinja2
- Frontend: minimal HTML + CSS (no React)

---

## Architecture

- `routes/` → HTTP endpoints (Robyn)
- `services/` → core logic (profiling, heuristics, file reading)
- `templates/` → Jinja templates
- `static/` → CSS only

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
- Always use:
  df.sample(n=10, seed=42)

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
- Keep layout simple:
  - summary
  - warnings
  - table
  - sample

Tables:
- truncate long text
- no sorting/filtering/pagination

---

## File Handling

- Accept:
  - CSV
  - Parquet

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
  - APIs beyond current scope

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

- Ensure app runs locally
- Test with:
  - small CSV
  - small Parquet
- Verify:
  - summary renders
  - sample renders
  - no crashes

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

## Final Rule

This project is intentionally **small and focused**.

If a change makes it:
- heavier
- slower
- more complex

→ do not implement it.
