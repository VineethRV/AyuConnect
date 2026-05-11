"""FastAPI app entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .routes import chat, report, triage

settings = get_settings()
app = FastAPI(
    title="AyuConnect — Gemma 4 Diagnostic Assistant",
    version=__version__,
    description=(
        "On-device, multimodal, tool-using medical intake powered by Gemma 4. "
        "Deployable to laptops, edge devices, and Kaggle notebooks with one env var."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(triage.router)
app.include_router(report.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "backend": settings.backend.value,
        "model_id": settings.model_id,
        "version": __version__,
    }


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": "AyuConnect",
        "tagline": "Gemma 4 powered medical intake — runs anywhere, even offline.",
        "docs": "/docs",
        "health": "/health",
    }
