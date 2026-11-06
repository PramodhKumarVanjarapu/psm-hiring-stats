"""Bucket (offline attended) and TR (assessment) pool files.

Uploaded from the Settings page and stored gzip-compressed in MongoDB (`pools` collection).
Files in backend/data/ or /etc/secrets/ are used when nothing was uploaded yet.
"""
from __future__ import annotations

import gzip
import threading
from pathlib import Path

from bson import Binary

from ..normalize import now_utc
from . import core

POOL_FILES = {"bucket": "offline_attended_pool.csv", "tr": "assessment_pool_main.csv"}
POOL_TITLES = {"bucket": "Bucket pool (offline attended)", "tr": "TR pool (assessment)"}
MAX_COMPRESSED = 15 * 1024 * 1024
_cache: dict = {}
_lock = threading.Lock()


def _file_fallback(kind: str) -> bytes | None:
    for folder in (Path(__file__).resolve().parents[2] / "data", Path("/etc/secrets")):
        p = folder / POOL_FILES[kind]
        if p.exists():
            return p.read_bytes()
    return None


def validate(kind: str, data: bytes) -> int:
    """Check the CSV has what the analysis needs; returns the row count."""
    df = core.read_csv_bytes(data)
    if kind == "bucket":
        if not core.find_col(df, ["bucket"]):
            raise ValueError("The bucket pool file needs a 'Bucket' column.")
    else:
        if not (core.find_col(df, ["tr1status"]) or core.find_col(df, ["tr2status"])):
            raise ValueError("The TR pool file needs 'TR1 Status' / 'TR2 Status' columns.")
    if not any(core.find_col(df, kw) for kw in (core.UID_KW, core.MOBILE_KW, core.EMAIL_KW)):
        raise ValueError("The file needs a user id, mobile or email column.")
    return len(df)


def save_pool(db, kind: str, filename: str, data: bytes, user_email: str) -> dict:
    rows = validate(kind, data)
    packed = gzip.compress(data)
    if len(packed) > MAX_COMPRESSED:
        raise ValueError("The file is too large (over 15 MB even after compression).")
    doc = {"_id": kind, "filename": filename, "rows": rows, "size_bytes": len(data),
           "uploaded_at": now_utc(), "uploaded_by": user_email, "data": Binary(packed)}
    db.pools.replace_one({"_id": kind}, doc, upsert=True)
    with _lock:
        _cache.clear()
    return pool_info(db)[kind]


def pool_info(db) -> dict:
    out = {}
    for kind in POOL_FILES:
        d = db.pools.find_one({"_id": kind}, {"data": 0})
        if d:
            out[kind] = {"title": POOL_TITLES[kind], "source": "uploaded", "filename": d["filename"],
                         "rows": d["rows"], "uploaded_at": d["uploaded_at"], "uploaded_by": d["uploaded_by"]}
        else:
            out[kind] = {"title": POOL_TITLES[kind],
                         "source": "file" if _file_fallback(kind) else "missing",
                         "filename": POOL_FILES[kind]}
    return out


def load_pools(db) -> dict:
    """core.build_pools(...) result, cached until a new file is uploaded."""
    raw, stamp = {}, []
    for kind in POOL_FILES:
        d = db.pools.find_one({"_id": kind})
        if d:
            raw[kind] = gzip.decompress(bytes(d["data"]))
            stamp.append(str(d["uploaded_at"]))
        else:
            data = _file_fallback(kind)
            if data is None:
                raise RuntimeError(f"{POOL_TITLES[kind]} is missing. Upload it on the Settings page.")
            raw[kind] = data
            stamp.append("file")
    key = "|".join(stamp)
    with _lock:
        if key not in _cache:
            _cache.clear()
            _cache[key] = core.build_pools(core.read_csv_bytes(raw["bucket"]), core.read_csv_bytes(raw["tr"]))
        return _cache[key]
