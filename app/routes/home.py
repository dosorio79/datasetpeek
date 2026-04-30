from __future__ import annotations

from robyn import Robyn
from robyn.templating import JinjaTemplate

from app.services.profiler import empty_view_model


def register_home_routes(*, app: Robyn, templates: JinjaTemplate) -> None:
    """Register the upload-first home page route."""

    @app.get("/")
    def home():
        return templates.render_template("home.html", **empty_view_model())
