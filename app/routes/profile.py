from __future__ import annotations

from robyn import Robyn
from robyn.templating import JinjaTemplate

from app.services.file_reader import FileValidationError, UploadedFile, read_uploaded_file
from app.services.profiler import build_profile_view_model, empty_view_model
from app.services.session_store import InMemoryUploadStore


def register_profile_routes(*, app: Robyn, templates: JinjaTemplate, upload_store: InMemoryUploadStore) -> None:
    """Register upload analysis and sample-resampling routes."""

    @app.post("/analyze")
    def analyze(request=None, files=None, form_data=None):
        try:
            preferred_filename = (form_data or {}).get("dataset_name")
            uploaded_file = UploadedFile.from_request_files(files, request=request, preferred_filename=preferred_filename)
            dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)
            token = upload_store.save(uploaded_file)
            context = build_profile_view_model(
                uploaded_file=uploaded_file,
                dataframe=dataframe,
                read_time_ms=read_time_ms,
                warnings=warnings,
                upload_token=token,
                sample_seed=42,
            )
        except FileValidationError as exc:
            context = empty_view_model(error_message=str(exc))

        return templates.render_template("home.html", **context)

    @app.post("/resample")
    def resample(form_data=None):
        token = (form_data or {}).get("upload_token", "")
        seed_text = (form_data or {}).get("resample_seed", "42")

        try:
            sample_seed = int(seed_text)
        except (TypeError, ValueError):
            sample_seed = 42

        uploaded_file = upload_store.get(token)
        if uploaded_file is None:
            context = empty_view_model(
                error_message="The uploaded file is no longer available. Upload it again to resample."
            )
            return templates.render_template("home.html", **context)

        try:
            dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)
            context = build_profile_view_model(
                uploaded_file=uploaded_file,
                dataframe=dataframe,
                read_time_ms=read_time_ms,
                warnings=warnings,
                upload_token=token,
                sample_seed=sample_seed,
            )
        except FileValidationError as exc:
            context = empty_view_model(error_message=str(exc))

        return templates.render_template("home.html", **context)
