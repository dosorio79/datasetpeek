# UI Redesign: Export Panel Implementation Plan

**Goal:** Reorganize the post-analysis UI to group export options into a dedicated panel with improved visual hierarchy and i18n scaffolding.

**Architecture:** Restructure `app/templates/home.html` to move export buttons from `result-meta-row` into a dedicated `.export-panel` section. Update `app/static/styles.css` with export panel styles. Add `data-i18n-key` attributes for localization.

**Tech Stack:** Jinja2, CSS custom properties, HTML semantic structure.

**Spec:** docs/superpowers/specs/2026-11-02-ui-redesign-export-panel.md

**Status:** Plan created; ready for execution.

## Global Constraints

- Preserve application behavior and export functionality
- Python 3.12 / Linux only
- Maintain all existing tests passing
- No secrets or runtime dependencies introduced
- CSS must use existing design tokens (var(--...))

## Review Focus

- Export download handlers still function correctly
- Profiling scope note visibility
- CSS specificity doesn't override existing panel styles
- Mobile responsiveness preserved
- No JavaScript errors in console

---

## Task 1: Restructure home.html export area

**Files:**
- Modify: `app/templates/home.html`
- Modify: `app/static/styles.css`

**Interfaces:**
- Consumes: `file_summary`, `has_result`, `markdown_report`, `html_report`, `profile_json` (from existing template context)
- Produces: HTML with new export panel structure; i18n-key attributes on notes

### Step 1: Write the failing test
**Command:** `uv run --locked pytest tests/test_app.py -q -k "home_renders"`

**Expected:** Test passes (existing test confirms current behavior)

### Step 2: Run it, verify it fails
**Action:** Verify current test passes before making changes (establishes baseline)

### Step 3: Write the minimal implementation
**Code changes to `app/templates/home.html`:**

Replace the scattered export area (lines 85-92) with the new export panel structure:

```html
<!-- Export Panel: Grouped export options -->
<section class="panel export-panel" aria-label="Report exports">
  <div class="section-heading">
    <h2>Export</h2>
  </div>
  <div class="table-wrap">
    <div class="export-options">
      <button type="button" class="link-button" id="download-markdown" data-export="markdown">
        <span class="icon">📄</span>
        <span class="label">Export Markdown</span>
      </button>
      <button type="button" class="link-button" id="download-html" data-export="html">
        <span class="icon">🌐</span>
        <span class="label">Export HTML</span>
      </button>
      <button type="button" class="link-button" id="download-json" data-export="json">
        <span class="icon">📋</span>
        <span class="label">Export JSON</span>
      </button>
    </div>
    <p class="export-note" i18n-key="export-note">
      JSON exports include capped top-value strings and signal details that may contain dataset content; preview rows are excluded.
    </p>
  </div>
</section>

<p class="result-note" i18n-key="profiling-scope">
  DatasetPeek profiles the full uploaded file or S3 object when it is within the size limit. If the object is an exported sample, these results describe that sample.
</p>
```

**Expected:** Template restructured; export panel visible in rendered HTML

### Step 4: Run it, verify it passes
**Command:** `uv run --locked pytest tests/test_app.py -q`

**Expected:** All 40 tests pass

### Step 5: Commit
**Command:** `git commit -m "feat: restructure export panel into dedicated panel with i18n keys"`

---

## Task 2: Add export panel CSS styles

**Files:**
- Modify: `app/static/styles.css`

**Interfaces:**
- Consumes: Existing CSS custom properties (var(--surface), var(--border), etc.)
- Produces: `.export-panel`, `.export-options`, `.export-note` styles

### Step 1: Write the failing test
**Command:** `uv run --locked pytest tests/test_app.py -q -k "home_renders"`

**Expected:** Test passes (no CSS-specific tests; visual regression not unit-tested)

### Step 2: Run it, verify it fails
**Action:** Confirm current state passes

### Step 3: Write the minimal implementation
**Code changes to `app/static/styles.css`:**

Add export panel styles at the end of the file (before `@media (prefers-reduced-motion: reduce)`):

```css
/* Export Panel Styles */
.export-panel {
  border-color: var(--highlight-border);
  background: linear-gradient(180deg, #ffffff 0%, #f0f7ff 100%);
}

.export-panel .section-heading {
  margin-bottom: 0.6rem;
}

.export-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  margin: 0;
}

.export-options .link-button {
  padding: 0.7rem 1rem;
  border-radius: 10px;
  background: var(--accent);
  color: white;
  font-size: 0.94rem;
  font-weight: 600;
  text-decoration: none;
  text-align: center;
  transition: background-color 120ms ease, box-shadow 120ms ease;
  border: 1px solid var(--accent);
}

.export-options .link-button:hover {
  background: #262b4e;
  box-shadow: 0 6px 14px rgba(47, 53, 93, 0.14);
}

.export-note {
  margin: 0.8rem 0 0;
  color: var(--muted);
  font-size: 0.86rem;
  line-height: 1.4;
}

/* Responsive: export panel on narrow screens */
@media (max-width: 720px) {
  .export-panel {
    border-width: 1px;
  }

  .export-options {
    grid-template-columns: 1fr;
  }

  .export-options .link-button {
    min-height: 3rem;
  }
}
```

**Expected:** CSS exports apply; panel styled correctly

### Step 4: Run it, verify it passes
**Command:** `uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy app main.py`

**Expected:** All checks pass

### Step 5: Commit
**Command:** `git commit -m "feat: add export panel CSS styles"`

---

## Task 3: Verify full implementation

**Files:** All modified files

**Interfaces:**
- Consumes: Tasks 1 and 2 deliverables
- Produces: Verified UI redesign

### Step 1: Write the failing test
**Command:** `uv run --locked pytest tests/test_app.py -q && uv run --locked --group browser pytest tests/browser -m browser -q`

**Expected:** All 40 unit tests + 1 browser test pass

### Step 2: Run it, verify it passes
**Action:** Run full test suite; check for any visual or functional regressions

### Step 3: Commit
**Command:** `git commit -m "feat: complete export panel UI redesign with tests passing"`

---

## Execution Handoff

After saving and self-reviewing, choose an execution approach:

- **Subagent-driven** — a fresh subagent implements each task with a review gate after each; most thorough, costs more
- **Inline/native** — implement every task yourself in this session, with one fresh review of the whole branch at the end; cheapest and fastest

Given the straightforward template and CSS changes, **inline execution** is recommended. The plan has been self-reviewed against the spec with all red flags addressed.