# PRD — DatasetPeek
### Fast, minimal profiler for CSV & Parquet

---

## 1. Product Overview

**Name:** DatasetPeek  
**Type:** Single-page web app  
**Current version:** 0.4.1

**Goal:**
> Understand a dataset in seconds.

**Core principles:**
- Fast  
- Minimal  
- Representative (not exhaustive)  
- Signal > noise  

---

## 2. Version Roadmap

### 0.4.0 — Previous Version

Deterministic triage core for local CSV/Parquet files and configured S3-compatible objects, with role hints, stronger quality signals, and portable human-readable reports.

Focus:
- dataset orientation summary
- column role detection
- stronger deterministic data quality signals
- capped categorical top values
- lightweight next-check guidance
- Markdown report download
- self-contained HTML report download
- environment-backed operational settings
- avoid charts, correlations, dashboards, and exploratory workflows

---

### 0.4.1 — Current Version / Demo Readiness Patch

This patch keeps the 0.4.0 triage behavior unchanged while tightening the public demo surface.

Goal:

> Make the existing triage workflow safer and cleaner to share.

Committed scope:
- render cycled sample rows without assigning uploaded values through `innerHTML`
- add social preview metadata for shared app links
- update package, lockfile, README, changelog, PRD, and example report versions

Explicitly deferred from 0.4.1:
- JSON export
- schema comparison
- larger-file/streaming performance work
- YAML/settings-file support
- UI-managed tuning
- configurable heuristic thresholds

Implementation blocks:
1. Lock this PRD scope.
2. Remove the sample cycling `innerHTML` sink.
3. Add social preview metadata.
4. Update versioned release documentation.
5. Prepare the 0.4.1 release.

Acceptance details:
- sample cycling preserves text rendering for uploaded dataset values
- social metadata does not add external assets or scripts
- patch release metadata is synchronized across package files and docs

This version should improve demo readiness without adding full EDA behavior, persistence, or new workflows.

---

### 0.5.0 — Model Export

The following version should make DatasetPeek profiles portable for automation, review, and downstream tooling without exporting raw dataset rows.

Goal:

> Give users a compact, versioned profile model they can pass to other tools.

Committed scope:
- downloadable `profile-model.json`
- explicit `schema_version`
- file summary
- column names, dtypes, inferred roles, completeness, and uniqueness
- deterministic signals
- capped top values
- orientation summary
- next checks
- report metadata such as DatasetPeek version and generated timestamp

Explicitly excluded from 0.5.0:
- raw data export
- random sample rows by default
- full report JSON with presentation-only fields
- schema comparison
- persistence or saved profile history

Implementation notes:
- generate JSON from the same structured profile model used by 0.4.0 reports
- treat the JSON shape as a versioned contract
- keep the export deterministic and compact
- avoid exposing internal template or view-model fields

This version should make the 0.4.0 triage model reusable without turning DatasetPeek into a data extraction or persistence tool.

---

### 1.0.0 — Stable First-Contact Profiler

A polished, reliable version of DatasetPeek once the core first-contact profiling experience is complete and stable.

A `1.0.0` release should represent:
- stable CSV and Parquet handling
- reliable profiling heuristics
- clear error handling
- predictable performance within documented file limits
- a clean, minimal interface suitable for repeated technical use

---

## 3. Problem

Users frequently receive datasets and need a **quick first-pass understanding**:
- structure  
- data types  
- data quality  
- potential modeling signals  

Existing tools:
- too slow (heavy profiling)  
- too verbose (report overload)  
- too exploratory (not focused on orientation)  

---

## 4. Target Users

- Data scientists  
- Data analysts  
- Data engineers  
- Technical users handling ad hoc datasets  

---

## 5. Key Use Case

> “I just received this file — tell me what I’m looking at.”

---

## 6. 0.3.x Current Scope

### Input
- Upload:
  - CSV  
  - Parquet  
- S3-compatible object URI:
  - CSV
  - Parquet

### File Constraints
- Recommended max size: **≤ 50–100 MB**  
- Files above **100 MB** are rejected before parsing  
- Files above **50 MB** may show a large-file warning  

---

## 7. Output (Single Page)

---

### 7.1 File Summary

- filename  
- file type (CSV / Parquet)  
- number of rows  
- number of columns  
- read time (ms)  

---

### 7.2 Data Quality Signals (Core Feature)

Heuristic-driven insights per column:

- possible ID column  
- mostly missing (>50%)  
- low variance column (top value ≥ 95%)  
- high cardinality text  
- likely categorical (low cardinality)  
- binary / potential target flag  
- suspicious mixed types  
- boolean disguised as string  

#### Binary / Potential Target

Flag if:
- exactly 2 unique values (excluding nulls)  
**OR**
- 2 dominant values covering ~100%  

Display with distribution:

> churn_flag → binary (1: 8.2%, 0: 91.8%)

---

#### Low Variance

- compute top value frequency ratio  
- flag if ≥ 0.95  
- ignore nulls  

Display:

> status → "active" (97.3%)

---

### 7.3 Column Overview Table

Per column:

- name  
- inferred dtype  
- non-null %  
- missing %  
- unique count  
- sample values (2–3)  

---

### 7.4 Numeric Summary

For numeric columns (int + float only):

- min  
- max  
- mean  
- median  

---

### 7.5 Data Preview

#### Primary:
**Random Sample**

- 10 rows  
- labeled: “Sample rows (random)”  

#### Interaction:
- Next sample button cycling through deterministic random samples  

#### Secondary (collapsed):
- Head (first 5 rows)  
- Tail (last 5 rows)  

---

## 8. UX Structure

~~~
Upload
→ File Summary
→ Data Quality Signals
→ Column Overview
→ Sample Data
→ (Optional) Head & Tail
~~~

**UX principles:**
- single page  
- no tabs  
- minimal interaction  
- immediate rendering  
- clean hierarchy  

---

## 9. Heuristics Definitions

### Possible ID
- uniqueness ratio ≈ 1.0  
- column name contains: `id`, `key`, `code`  

---

### Mostly Missing
- missing > 50%  

---

### Low Variance
- top value frequency ≥ 0.95  

---

### Likely Categorical
- low cardinality relative to row count  

---

### High Cardinality Text
- high unique count  
- string dtype  

---

### Binary / Potential Target
- exactly 2 unique values  
**OR**  
- 2 dominant values  

---

### Boolean-like
- values resemble:
  - yes/no  
  - true/false  
  - 0/1  

---

### Mixed Types
- inconsistent parsing  
- numeric-like values inside string columns  

---

## 10. Technical Design

### Stack

- **Backend:** Robyn  
- **Processing:** Polars  
- **Templating:** Jinja2  
- **Frontend:** HTML + minimal CSS + vanilla JavaScript  

---

### Folder Structure

~~~
app/
  main.py
  routes/
    home.py
    profile.py
  services/
    file_reader.py
    profiler.py
    heuristics.py
    s3_reader.py
    settings.py
  templates/
    base.html
    home.html
  static/
    styles.css
~~~

---

### Processing Flow

1. Upload file or provide S3-compatible object URI  
2. Detect format (CSV / Parquet)  
3. Load with Polars  
4. Compute:
   - schema  
   - null counts  
   - unique counts  
   - top value stats  
5. Apply heuristics  
6. Generate preview:
   - sample (random)  
   - head/tail  
7. Render via Jinja template  

---

### CSV Handling (MVP Assumptions)

- delimiter: auto or default comma  
- header: assumed present  
- parsing fallback: string if needed  

---

### Sampling Strategy

- full dataset loaded (within size constraint)  
- deterministic random sample set:

~~~python
df.sample(n=10, seed=42)
df.sample(n=10, seed=43)
df.sample(n=10, seed=44)
df.sample(n=10, seed=45)
~~~

---

## 11. Performance Principles

- compute only essential stats  
- reuse aggregates across heuristics  
- avoid full distributions  
- keep preview small (10 rows)  
- optimize for perceived speed  

---

## 12. UI Constraints

- truncate long text (~50 chars)  
- horizontal scroll for wide tables  
- simple tables (no sorting/filtering)  

---

## 13. Error Handling (Minimal)

- unsupported file → message  
- parsing failure → fallback / error  
- empty file → message  

---

## 14. Non-Goals (Strict)

- correlations  
- charts / histograms  
- pairwise analysis  
- filtering / sorting UI  
- pagination  
- authentication  
- persistence  
- full EDA reports  

---

## 15. Success Criteria

- dataset understood in <10 seconds  
- key signals visible immediately  
- UI is clean and uncluttered  
- app feels fast and responsive  

---

## 16. Future Extensions

- versioned profile-model JSON export
- schema comparison from saved `profile-model.json` exports as a natural 0.6.0 candidate
- larger-file/streaming performance  
- YAML/settings-file support  
- UI-managed tuning  
- drift detection  
- join key suggestions  
- RAG integration  

---

## 17. Positioning

> DatasetPeek is not an EDA tool.  
> It is a **first-contact data profiler**.

---

## 18. Build Scope

- achievable in **1–2 focused sessions**  
- no infrastructure complexity  
- ideal for learning **Robyn + Polars + Jinja2** through a real use case  
