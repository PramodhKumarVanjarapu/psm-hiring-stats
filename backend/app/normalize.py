"""Cleaning helpers, so the same person / job always gets the same key."""
from __future__ import annotations

import re
from datetime import datetime, timezone

JUNK = {"", "nan", "none", "null", "-", "#ref!", "#n/a", "na", "n/a"}

STAGES = ("TA", "RS", "SC", "AS", "SP")
TA_LABEL = "Applied"
OTHER_LABEL = "Other / blank"

# Lower rank = better. Used when the same person appears more than once in a stage.
LABEL_RANK = {TA_LABEL: 0, "P1": 1, "P2": 2, "P3": 3, "Select": 4, "Hold": 5, "Reject": 6,
              "NA": 7, OTHER_LABEL: 8}
CATEGORY_RANK = {"Intensive": 0, "Academy": 1, "External": 2}


def is_junk(x) -> bool:
    return x is None or str(x).strip().lower() in JUNK


def clean_text(x) -> str | None:
    return None if is_junk(x) else re.sub(r"\s+", " ", str(x).strip())


def norm_mobile(x) -> str | None:
    """Last 10 digits ('+91 98765 43210', '919876543210', '9876543210.0' -> '9876543210')."""
    if is_junk(x):
        return None
    s = str(x).strip()
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]
    digits = re.sub(r"\D", "", s)
    return digits[-10:] if len(digits) >= 10 else None


def norm_email(x) -> str | None:
    if is_junk(x):
        return None
    s = str(x).strip().lower()
    return s if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s) else None


def norm_user_id(x) -> str | None:
    if is_junk(x):
        return None
    return re.sub(r"\s+", "", str(x).strip().lower())


def job_key(job_id: str) -> str:
    """' j-1234 ' and 'J-1234' are the same job."""
    return re.sub(r"\s+", " ", str(job_id).strip()).upper()


def norm_bucket(x) -> str | None:
    """'Bucket A', 'bucket-a', 'a' -> 'A'; other non-blank values are kept as written."""
    if is_junk(x):
        return None
    s = re.sub(r"[^A-Z0-9]+", " ", re.sub(r"BUCKET", " ", str(x).upper())).strip()
    if s in ("A", "B", "C", "D"):
        return s
    m = re.search(r"\b([A-D])\b", s)
    return m.group(1) if m else clean_text(x)


def better_label(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if LABEL_RANK.get(a, 50) <= LABEL_RANK.get(b, 50) else b


def better_category(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if CATEGORY_RANK.get(a, 9) <= CATEGORY_RANK.get(b, 9) else b


def furthest_stage(stages: dict) -> str | None:
    last = None
    for s in STAGES:
        if stages.get(s) is not None:
            last = s
    return last


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
