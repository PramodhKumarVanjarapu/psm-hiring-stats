"""Applicant Analytics API (FastAPI + MongoDB), used by the React app.

Run locally:  uvicorn app.main:app --reload --env-file .env
Interactive docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import ensure_admin
from .config import settings
from .db import ensure_indexes, get_db
from .routers import analyses, auth, jobs, reports, settings as settings_router, students

log = logging.getLogger("analytics-api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = get_db()
    ensure_indexes(db)
    ensure_admin(db)
    if not settings.jwt_secret:
        log.warning("JWT_SECRET is not set: nobody can log in until it is.")
    yield


app = FastAPI(title="Applicant Analytics API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for r in (auth.router, analyses.router, jobs.router, students.router, reports.router, settings_router.router):
    app.include_router(r)


@app.get("/health")
def health():
    try:
        get_db().command("ping")
        return {"status": "ok", "database": "ok"}
    except Exception as exc:  # pragma: no cover
        log.warning("database ping failed: %s", exc)
        raise HTTPException(503, "Database not reachable.")
