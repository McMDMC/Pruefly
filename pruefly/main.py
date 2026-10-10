"""FastAPI app. Stateless: nothing a teacher uploads or generates is stored."""
from __future__ import annotations

import base64
import binascii
import logging
import re
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .config import Settings
from .ir import pipeline
from .ir.schema import IR
from .llm.base import AllProvidersFailed, ImageInput, ModelRouter
from .llm.factory import build_router
from .render.html import render_html
from .security import RateLimiter, check_access, client_key, sniff_image

log = logging.getLogger("pruefly")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
JSON_LIMIT = 1_000_000

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "frame-src 'self' about:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class AnalyzeIn(BaseModel):
    image_b64: str = Field(min_length=100)


class TransformIn(BaseModel):
    ir: IR
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class RenderIn(BaseModel):
    ir: IR
    solution: bool = False
    format: str = Field(default="html", pattern="^(html|pdf)$")


def create_app(settings: Settings | None = None, router: ModelRouter | None = None) -> FastAPI:
    s = settings or Settings.from_env()
    app = FastAPI(title="Prüfly", docs_url=None, redoc_url=None, openapi_url=None)
    limiter = RateLimiter(s.rate_limit_per_hour)
    state = {"router": router}
    max_body = int(s.max_image_bytes * 4 / 3) + 4096

    def get_router() -> ModelRouter:
        if state["router"] is None:
            state["router"] = build_router(s)
        return state["router"]

    async def auth(request: Request) -> None:
        check_access(s, request)

    async def limited(request: Request) -> None:
        check_access(s, request)
        limiter.hit(client_key(request))

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method == "POST":
            cl = request.headers.get("content-length")
            if cl is None or not cl.isdigit():
                return JSONResponse({"detail": "Content-Length fehlt."}, status_code=411)
            limit = max_body if request.url.path == "/api/analyze" else JSON_LIMIT
            if int(cl) > limit:
                return JSONResponse({"detail": "Anfrage zu groß."}, status_code=413)
        resp = await call_next(request)
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/config")
    async def config():
        return {"auth_required": bool(s.access_code) or not s.is_dev, "configured": bool(s.access_code) or s.is_dev}

    @app.post("/api/check", dependencies=[Depends(auth)])
    async def check():
        return {"ok": True}

    @app.post("/api/analyze", dependencies=[Depends(limited)])
    async def analyze(body: AnalyzeIn):
        try:
            raw = base64.b64decode(body.image_b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, "Bild ungültig.") from None
        if len(raw) > s.max_image_bytes:
            raise HTTPException(413, "Bild zu groß.")
        media = sniff_image(raw)
        if media is None:
            raise HTTPException(415, "Bitte ein Foto (JPEG, PNG oder WebP) hochladen.")
        try:
            ir, report, provider = await pipeline.analyze(get_router(), ImageInput(raw, media))
        except AllProvidersFailed as exc:
            log.error("analyze failed: %s", exc)
            raise HTTPException(502, "Das Foto konnte nicht ausgewertet werden. Bitte erneut versuchen.") from None
        return {"ir": ir.model_dump(), "report": report, "provider": provider}

    @app.post("/api/transform", dependencies=[Depends(limited)])
    async def transform(body: TransformIn):
        new, warnings, provider = await pipeline.transform(get_router(), body.ir, body.seed)
        return {"ir": new.model_dump(), "warnings": warnings, "provider": provider}

    @app.post("/api/render", dependencies=[Depends(auth)])
    async def render(body: RenderIn):
        if body.format == "html":
            return {"html": render_html(body.ir, body.solution)}
        from .render.pdf import render_pdf

        pdf = await run_in_threadpool(render_pdf, body.ir, body.solution)
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", body.ir.title.encode("ascii", "ignore").decode()).strip("_") or "Arbeitsblatt"
        suffix = "_Loesung" if body.solution else ""
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}{suffix}.pdf"'})

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def app_factory() -> FastAPI:  # uvicorn --factory pruefly.main:app_factory
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app()
