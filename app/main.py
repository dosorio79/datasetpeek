from __future__ import annotations

from pathlib import Path

from robyn import Robyn, Response
from robyn.templating import JinjaTemplate

from app.routes.home import register_home_routes
from app.routes.profile import register_profile_routes
from app.services.session_store import InMemoryUploadStore

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = JinjaTemplate(str(BASE_DIR / "templates"))
UPLOAD_STORE = InMemoryUploadStore()
LOGO_PATH = BASE_DIR / "img" / "datapeek-logo.png"
FAVICON_ICO_PATH = BASE_DIR / "static" / "favicon.ico"
FAVICON_PNG_PATH = BASE_DIR / "static" / "favicon-32.png"
APPLE_TOUCH_ICON_PATH = BASE_DIR / "static" / "apple-touch-icon.png"


def create_app() -> Robyn:
    """Create the Robyn app and register DataPeek's small route surface."""

    # Robyn needs the module file path so it can anchor internal configuration.
    app = Robyn(__file__)

    register_home_routes(app=app, templates=TEMPLATES)
    register_profile_routes(app=app, templates=TEMPLATES, upload_store=UPLOAD_STORE)

    @app.get("/health")
    def health() -> Response:
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json; charset=utf-8"},
            description='{"status":"ok"}',
        )

    @app.get("/static/styles.css")
    def styles() -> Response:
        stylesheet = (BASE_DIR / "static" / "styles.css").read_text(encoding="utf-8")
        return Response(
            status_code=200,
            headers={"Content-Type": "text/css; charset=utf-8"},
            description=stylesheet,
        )

    @app.get("/static/logo.png")
    def logo() -> Response:
        return Response(
            status_code=200,
            headers={"Content-Type": "image/png", "Cache-Control": "no-store"},
            description=LOGO_PATH.read_bytes(),
        )

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(
            status_code=200,
            headers={"Content-Type": "image/x-icon", "Cache-Control": "no-store"},
            description=FAVICON_ICO_PATH.read_bytes(),
        )

    @app.get("/static/favicon-32.png")
    def favicon_png() -> Response:
        return Response(
            status_code=200,
            headers={"Content-Type": "image/png", "Cache-Control": "no-store"},
            description=FAVICON_PNG_PATH.read_bytes(),
        )

    @app.get("/static/apple-touch-icon.png")
    def apple_touch_icon() -> Response:
        return Response(
            status_code=200,
            headers={"Content-Type": "image/png", "Cache-Control": "no-store"},
            description=APPLE_TOUCH_ICON_PATH.read_bytes(),
        )

    return app


app = create_app()


def run(*, host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the module-level app with deployment-friendly host and port values."""

    app.start(host=host, port=port)
