"""Analyses run in the background: create -> (queued, running) -> done | failed -> saved.

The React app polls GET /api/v1/analyses/{id} for progress. The full result (stats + every
candidate row) is stored gzip-compressed, so "Save" works even after a server restart.
"""
from __future__ import annotations

import gzip
import json
import logging
import secrets
import traceback
from datetime import timedelta

from bson import Binary

from ..config import settings
from ..normalize import as_utc, now_utc
from ..schemas import RunIn
from ..service import save_run
from . import engine
from .pools import load_pools
from .sheets import service_account_email, sheets_client

log = logging.getLogger("analytics-api")
KEEP_UNSAVED = timedelta(days=7)
STALE_AFTER = timedelta(minutes=20)


def create_analysis(db, job_id: str, sheet_url: str, company: str | None, role: str | None, user: dict) -> dict:
    if "docs.google.com/spreadsheets" not in sheet_url:
        raise ValueError("Enter a valid Google Sheets link.")
    now = now_utc()
    doc = {"_id": secrets.token_hex(16), "job_id": job_id.strip(), "sheet_url": sheet_url.strip(),
           "company": (company or "").strip() or None, "role": (role or "").strip() or None,
           "status": "queued", "message": "Waiting to start", "created_by": user["_id"],
           "created_at": now, "updated_at": now, "expires_at": now + KEEP_UNSAVED}
    db.analyses.insert_one(doc)
    return public(doc)


def _set(db, aid: str, **fields) -> None:
    db.analyses.update_one({"_id": aid}, {"$set": {**fields, "updated_at": now_utc()}})


def _friendly(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc)
    if isinstance(exc, (engine.SheetError, ValueError)):
        return text
    if name == "SpreadsheetNotFound" or "404" in text:
        return "The sheet was not found. Check the link."
    if "403" in text or "PERMISSION_DENIED" in text or "permission" in text.lower():
        email = service_account_email()
        return (f"The sheet is not shared with the service account. Share it with {email} (Viewer)."
                if email else "The sheet is not shared with the service account.")
    return f"{name}: {text}"


def run_analysis(db, aid: str, book_opener=None) -> None:
    """Runs in a background thread. `book_opener(url)` can be replaced in tests."""
    doc = db.analyses.find_one({"_id": aid})
    if not doc:
        return
    try:
        _set(db, aid, status="running", message="Opening the sheet")
        opener = book_opener or (lambda url: sheets_client().open_by_url(url))
        book = opener(doc["sheet_url"])
        _set(db, aid, message="Loading bucket and TR pool files")
        pools = load_pools(db)
        result = engine.analyse(book, pools, doc["job_id"], progress=lambda m: _set(db, aid, message=m))
        packed = gzip.compress(json.dumps({"stages": result["stages"], "candidates": result["candidates"],
                                           "summary_row": result["summary_row"]}).encode())
        _set(db, aid, status="done", message="Ready to save", preview=result["preview"], data=Binary(packed))
    except Exception as exc:
        log.warning("analysis %s failed: %s\n%s", aid, exc, traceback.format_exc())
        _set(db, aid, status="failed", message=_friendly(exc))


def get_analysis(db, aid: str) -> dict | None:
    doc = db.analyses.find_one({"_id": aid}, {"data": 0})
    if not doc:
        return None
    if doc["status"] in ("queued", "running") and now_utc() - as_utc(doc["updated_at"]) > STALE_AFTER:
        _set(db, aid, status="failed", message="The analysis stopped (the server restarted). Run it again.")
        doc = db.analyses.find_one({"_id": aid}, {"data": 0})
    return public(doc)


def public(doc: dict) -> dict:
    return {"id": doc["_id"], "job_id": doc["job_id"], "sheet_url": doc["sheet_url"],
            "company": doc.get("company"), "role": doc.get("role"), "status": doc["status"],
            "message": doc.get("message"), "created_by": doc.get("created_by"),
            "created_at": doc.get("created_at"), "updated_at": doc.get("updated_at"),
            "preview": doc.get("preview"), "save_result": doc.get("save_result")}


def save_analysis(db, aid: str, user: dict) -> dict:
    doc = db.analyses.find_one({"_id": aid})
    if not doc:
        raise LookupError("Analysis not found.")
    if doc["status"] == "saved":
        return {**doc["save_result"], "status": "already_saved",
                "warnings": ["This analysis was already saved, so nothing was written again."]}
    if doc["status"] != "done" or not doc.get("data"):
        raise ValueError("This analysis is not ready to save.")
    data = json.loads(gzip.decompress(bytes(doc["data"])))
    run = RunIn(run_id=aid, job_id=doc["job_id"], company=doc.get("company"), role=doc.get("role"),
                sheet_url=doc["sheet_url"], sheet_title=(doc.get("preview") or {}).get("sheet_title"),
                run_at=doc["created_at"], tr_rule=engine.TR_RULE, stages=data["stages"],
                candidates=data["candidates"])
    result = save_run(db, run)

    if settings.master_sheet_url and result.get("status") == "saved":
        try:
            row = {**data["summary_row"], "Sheet URL": doc["sheet_url"]}
            engine.append_summary(sheets_client(), settings.master_sheet_url, row)
            result["master_sheet"] = "appended"
        except Exception as exc:
            result.setdefault("warnings", []).append(f"Saved, but the master Google Sheet was not updated: "
                                                     f"{_friendly(exc)}")
    _set(db, aid, status="saved", message="Saved", save_result=result, saved_by=user["_id"],
         expires_at=None)
    db.analyses.update_one({"_id": aid}, {"$unset": {"data": "", "expires_at": ""}})
    return result


def list_analyses(db, limit: int = 20) -> list[dict]:
    return [public(d) for d in db.analyses.find({}, {"data": 0, "preview": 0}).sort("created_at", -1).limit(limit)]
