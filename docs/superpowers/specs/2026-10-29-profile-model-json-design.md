# Profile Model JSON Export — Design Spec

**Status:** Implemented (pending release)
**Target release:** 0.5.0
**Date:** 2026-10-29

## Goal

Let users download a compact, versioned profile that can be reviewed or passed
to downstream tools, without turning DatasetPeek into a raw-data export or
persistence product.

## User experience

- Add an **Export JSON** action next to the existing Markdown and HTML report
  downloads on the results page.
- Download a file named `profile-model.json` from the already-built profile;
  do not re-read or re-profile the uploaded file.
- Follow the current client-side download pattern. This feature does not add an
  API route or require another request after profiling.

## Contract

The JSON is a public, versioned contract, built with a dedicated serializer
from `DatasetProfile`. Do not serialize the dataclass, template context, or
view model directly. The initial schema version is the string `"1.0.0"`.

Top-level structure:

```json
{
  "schema_version": "1.0.0",
  "metadata": {
    "datasetpeek_version": "0.5.0",
    "generated_at": "2026-10-29T12:00:00Z"
  },
  "file": {
    "filename": "customers.csv",
    "file_type": "CSV",
    "rows": 1200,
    "columns": 3,
    "read_time_ms": 18
  },
  "columns": [],
  "numeric_summary": [],
  "signals": [],
  "orientation": [],
  "next_checks": []
}
```

Fields:

- `schema_version`: semantic version for the export schema, independent of the
  DatasetPeek package version.
- `metadata.datasetpeek_version`: application/package version.
- `metadata.generated_at`: ISO 8601 UTC timestamp. It records serialization time when the result is built; repeated downloads from the same rendered result retain that timestamp. Across new results it may vary; the
  data-derived profile content, not the complete document bytes, is the
  deterministic portion of the contract. `read_time_ms` is also runtime-dependent.
- `file`: basename-only filename (strip local path or S3 URI prefixes, including Windows separators), uppercase file type, row and column counts, and read time.
- `columns`: one entry per input column, preserving input order. Each entry has
  `name`, `dtype`, `role`, `non_null_ratio`, `missing_ratio`, `unique_count`,
  and `top_values`.
- `top_values`: capped entries with `value` (string), `count` (integer), and
  `ratio` (number from 0 to 1). The configured cap is respected. Ratios use the non-null row count as denominator. Values retain the existing display formatting and truncation; they are not lossless source values.
- `numeric_summary`: entries with column `name` and numeric `min`, `max`,
  `mean`, and `median`. Use JSON `null` when a statistic is undefined; do not
  encode numeric values as display-formatted strings.
- `signals`: entries with `column`, `kind`, and `message` strings.
- `orientation` and `next_checks`: arrays of strings.
- `non_null_ratio`, `missing_ratio`, and `ratio` are fractions in `[0, 1]`,
  not percentages in `[0, 100]` and not percent-formatted strings. Numeric
  precision should preserve the calculated value rather than the UI's rounded
  presentation. Column ratios use total row count; both are zero for an empty
  frame. Integer statistics remain integers; Decimal statistics are converted
  to JSON-compatible numbers and may lose precision through float conversion.

## Data boundary and privacy

- Do not include raw preview/sample rows, head/tail rows, or per-column sample
  values.
- Include capped top-value strings and signal messages as stated above. They may
  contain values from the source dataset and may be sensitive; the UI must make
  this clear near the export action or via concise explanatory copy.
- Do not include credentials, S3 endpoint URLs, object URIs, local paths, or
  internal view-model/template fields. The exported filename is reduced to its
  basename, and occurrences of the source name in orientation, next-check, and
  signal text are replaced with that basename.
- Keep the existing upload size limits and in-memory processing model.

## Compatibility and evolution

- Adding optional fields without changing existing field meaning is compatible
  within schema major version 1.
- Removing/renaming fields, changing types or units, or changing semantic
  meaning requires a schema major-version increment.
- Keep schema version separate from the app version. Consumers must be able to
  branch on `schema_version`.
- No server-side profile storage or history is introduced.

## Out of scope

- Raw dataset or sample-row export.
- Schema comparison, profile ingestion, or saved history.
- A public JSON API endpoint.
- JSON import, arbitrary user-selectable fields, or configurable export
  thresholds.

## Acceptance criteria

1. A successful profile offers a JSON download alongside existing reports;
   invalid/empty upload states do not offer it.
2. The download is valid UTF-8 JSON, named `profile-model.json`, and has the
   documented top-level structure and `schema_version`.
3. The export is built from the same structured profile used by the UI/reports,
   preserves column order, uses numeric JSON types and ratio units, and omits
   preview/sample rows and sample values.
4. Capped top values remain capped, source URIs/paths are absent, and the
   interface discloses that top-value strings and signal details come from the
   dataset.
5. Undefined numeric statistics serialize as JSON `null`; output is safe for
   strict JSON parsers (no NaN or Infinity tokens).
6. Tests cover representative profile serialization, empty/undefined metrics,
   JSON download behavior, and the absence of raw preview rows.
7. Existing Markdown/HTML exports and profiling behavior remain unchanged.

## Decisions

- Use the existing client-side download interaction rather than adding a route.
- Include a timestamp as provenance; it is not part of deterministic profile
  content.
- Use JSON numbers for numeric metrics, with ratios represented as fractions.
- Include capped top-value strings, but exclude sample values and sample rows.
