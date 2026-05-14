from __future__ import annotations

from robyn import Robyn
from robyn.templating import JinjaTemplate

from app.services.file_reader import FileValidationError, UploadedFile, read_uploaded_file
from app.services.profiler import build_profile_view_model, empty_view_model


def register_profile_routes(*, app: Robyn, templates: JinjaTemplate) -> None:
    """Register upload analysis routes."""

    @app.post("/analyze")
    def analyze(request=None, files=None, form_data=None):
        try:
            form = form_data or {}
            s3_uri = (form.get("s3_uri") or "").strip()
            if s3_uri:
                uploaded_file = UploadedFile.from_s3_uri(s3_uri)
            else:
                preferred_filename = form.get("dataset_name")
                uploaded_file = UploadedFile.from_request_files(files, request=request, preferred_filename=preferred_filename)
            dataframe, read_time_ms, warnings = read_uploaded_file(uploaded_file)
            context = build_profile_view_model(
                uploaded_file=uploaded_file,
                dataframe=dataframe,
                read_time_ms=read_time_ms,
                warnings=warnings,
            )
        except FileValidationError as exc:
            context = empty_view_model(error_message=str(exc))

        return templates.render_template("home.html", **context)
