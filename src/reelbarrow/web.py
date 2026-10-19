from html import escape
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from reelbarrow.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="reelbarrow")

    @app.get("/healthz")
    def healthz() -> dict[str, str | bool]:
        return {"status": "ok", "dry_run": settings.dry_run}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        mode = (
            "Dry run: plans are recorded and nothing on the share is changed."
            if settings.dry_run
            else "Filing is live."
        )
        return (
            "<!doctype html><title>reelbarrow</title>"
            f"<h1>reelbarrow {escape(version('reelbarrow'))}</h1>"
            f"<p>{escape(mode)}</p>"
        )

    return app
