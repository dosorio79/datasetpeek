# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning tags.

## [0.3.2] - 2026-05-14

### Added
- Drag-and-drop upload support for local CSV and Parquet files.
- Loading feedback for dataset analysis with an in-button spinner and inline status text.

### Changed
- Strengthened the upload workflow with richer file selection feedback, improved source switch styling, and clearer submit-state hierarchy.
- Refined the page spacing, summary cards, and results presentation to make the app feel more tool-like and less flat.
- Added restrained teal highlight accents within the existing DatasetPeek visual style.
## [0.3.1] - 2026-05-14

### Added
- Backward-compatible support for legacy `DATAPEEK_*` environment variables during the DatasetPeek rename transition.

### Changed
- Renamed the product from DataPeek to DatasetPeek across the app, docs, package metadata, and repository configuration.
- Renamed the Render Blueprint service and Python package slug to `datasetpeek`.
- Regenerated the logo assets and updated the UI and README branding to DatasetPeek.

## [0.3.0] - 2026-05-10

### Added
- Dataset source switcher that separates local file uploads from S3/MinIO URI analysis.
- Clear source-picker copy for configured S3-compatible object stores such as MinIO, Cloudflare R2, and private S3.
- User-facing note that DatasetPeek profiles the full accepted file/object, while externally exported samples remain sample-level inputs.

### Changed
- Refined the opening upload layout into a compact `Analyze dataset` source picker.
- Improved S3 download errors for access denied, missing objects, and generic HTTP failures.
- README now documents the source switcher, Render environment variables for S3-compatible credentials, path-style endpoint behavior, and public-bucket caveats.

## [0.2.0] - 2026-05-05

### Added
- S3-compatible dataset input for CSV and Parquet objects.
- MinIO and custom S3 endpoint support through `DATASETPEEK_S3_ENDPOINT_URL`.
- Optional SigV4 request signing through S3 credential environment variables.
- UI input for analyzing `s3://bucket/path/file.csv` and `.parquet` objects.
- README-based help menu for local, S3, and MinIO usage.
- Tests for S3 URI parsing, MinIO-style path requests, signed headers, and route integration.

### Changed
- Split S3-compatible object reading into `app/services/s3_reader.py`.
- README now documents S3/MinIO dataset input and repository branch-protection operations.
- Branch protection documentation now treats Terraform as the source of truth.

## [0.1.2] - 2026-04-30

### Changed
- Multipart fallback parsing now selects only the `dataset` file part and no longer uses broad filename/payload slicing.
- Upload intake now rejects files above 100 MB before parsing or caching.
- Large-file warnings now start above 50 MB.
- Resample now renders validation errors instead of bubbling parse failures.
- Robyn route handlers no longer use annotations that break OpenAPI generation during deployment startup.

### Added
- Regression tests for raw multipart fallback, multi-part dataset selection, oversized upload rejection, resample validation errors, and OpenAPI route preparation.

## [0.1.1] - 2026-04-20

### Added
- Render deployment configuration via `render.yaml` for a single starter-tier web service.
- Lightweight `/health` endpoint for platform health checks.

### Changed
- Runtime startup now prefers `PORT` and `HOST` environment variables, with CLI flags still available as overrides.
- README now documents the Render deployment model, health check path, and the single-instance in-memory upload assumptions.
- Tests now cover the health endpoint and launcher runtime configuration behavior.

## [0.1.0] - 2026-04-15

### Added
- Initial DatasetPeek MVP built with Robyn, Polars, and Jinja2.
- CSV and Parquet upload with single-page profiling output.
- File summary, column overview, numeric summary, random sample, head, and tail views.
- Column-level signals for possible IDs, missingness, low variance, binary targets, boolean disguised as string, mixed types, and categorical/high-cardinality cues.
- Upload/resample flow, logo/favicons, Makefile, README, and GitHub Actions CI.
