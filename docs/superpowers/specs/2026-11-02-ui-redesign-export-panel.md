# UI Redesign: Export Panel Specification

**Goal:** Reorganize the post-analysis UI to group export options (Markdown, HTML, JSON) into a dedicated panel, improving visual hierarchy and localization readiness.

**Architecture:** The home template (`app/templates/home.html`) will be restructured to move export buttons from the scattered `result-meta-row` div into a dedicated `<section class="panel export-panel">` component. CSS styles (`app/static/styles.css`) will be updated to style the new panel. i18n scaffolding via `data-i18n-key` attributes will be added for future localization.

**Tech Stack:** Jinja2 templating, CSS custom properties, HTML semantic structure.

**Spec:** This specification implements the UI/UX feedback regarding export options being "lost between panels" and the need for redesign/localization.

## Global Constraints

- Preserve existing application behavior and runtime dependencies
- Maintain all existing export functionality (Markdown, HTML, JSON download)
- Keep profiling scope note contextual but visible
- Ensure all 40 existing tests continue to pass
- Python 3.12 / Linux compatibility
- No breaking changes to the Robyn route handlers or profile model

## Review Focus

- Export buttons must remain functional and accessible
- Profiling scope note must not be lost or hidden
- CSS must respect the existing design system (color vars, panel styles)
- i18n keys must not conflict with existing translation infrastructure
- Mobile-responsive design must remain intact (max-width: 720px media query)

## Successful Implementation Criteria

1. Export panel renders as a bordered panel with "Export" heading
2. Three export buttons (Markdown, HTML, JSON) are grouped together with icons
3. Profiling scope note appears below the export panel with i18n-key attribute
4. All existing tests pass (40 unit tests + 1 browser test)
5. Ruff and mypy checks pass
6. CSS is responsive down to 720px viewport width
7. No JavaScript functionality is broken (download handlers still work)