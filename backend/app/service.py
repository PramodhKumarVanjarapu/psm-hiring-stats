"""Saving one analytics run (job stats + students + applications)."""
from __future__ import annotations

import secrets
from datetime import timedelta

from pymongo import ReplaceOne, UpdateOne
from pymongo.errors import DuplicateKeyError

from .config import settings
from .identity import Conflict, StudentResolver, group_records
from .normalize import (STAGES, as_utc, better_category, better_label, furthest_stage, job_key,
                        now_utc)
from .schemas import RunIn


class SaveBusy(Exception):
    """Another save is running right now."""


class RunMismatch(Exception):
    """The run_id was already used for a different job."""


class IdentityClash(Exception):
    """A student key was written by someone else at the same moment."""


# --------------------------------------------------------------------------- #
# Save lock: one save at a time, so two saves never fight over the same student.
# --------------------------------------------------------------------------- #
LOCK_ID = "save"


def acquire_lock(db, now) -> str:
    token = secrets.token_hex(8)
    doc = {"_id": LOCK_ID, "token": token, "expires_at": now + timedelta(seconds=settings.lock_seconds)}
    try:
        db.locks.insert_one(doc)
        return token
    except DuplicateKeyError:
        current = db.locks.find_one({"_id": LOCK_ID})
        if current and as_utc(current["expires_at"]) < now:
            # A crashed save left the lock behind: take it over.
            db.locks.delete_one({"_id": LOCK_ID, "token": current["token"]})
            try:
                db.locks.insert_one(doc)
                return token
            except DuplicateKeyError:
                pass
        raise SaveBusy("Another save is in progress. Try again in a minute.")


def release_lock(db, token: str) -> None:
    db.locks.delete_one({"_id": LOCK_ID, "token": token})


# --------------------------------------------------------------------------- #
# Save
# --------------------------------------------------------------------------- #
def _duplicate_response(stats_doc: dict) -> dict:
    return {"status": "already_saved", "run_id": stats_doc["_id"], "job_id": stats_doc["job_id"],
            "is_latest": stats_doc.get("is_latest", False), **stats_doc.get("save_summary", {}),
            "warnings": ["This run was already saved earlier, so nothing was written again."]}


def save_run(db, run: RunIn) -> dict:
    now = now_utc()
    run_at = as_utc(run.run_at) or now
    jkey = job_key(run.job_id)

    existing = db.job_stats.find_one({"_id": run.run_id})
    if existing:
        if existing["job_key"] != jkey:
            raise RunMismatch(f"run_id {run.run_id} was already used for job {existing['job_id']}.")
        return _duplicate_response(existing)

    token = acquire_lock(db, now)
    try:
        existing = db.job_stats.find_one({"_id": run.run_id})  # saved while we waited?
        if existing:
            return _duplicate_response(existing)
        return _save_locked(db, run, jkey, run_at, now)
    finally:
        release_lock(db, token)


def _save_locked(db, run: RunIn, jkey: str, run_at, now) -> dict:
    warnings: list[str] = []
    job = db.jobs.find_one({"_id": jkey})
    latest = db.job_stats.find_one({"job_key": jkey}, sort=[("run_at", -1)])
    is_newest = latest is None or run_at >= as_utc(latest["run_at"])
    if not is_newest:
        warnings.append("A newer run of this job is already saved. This run was kept in the history "
                        "only; the job's latest numbers and student list did not change.")
    if job and run.sheet_url and job.get("sheet_urls") and run.sheet_url not in job["sheet_urls"]:
        warnings.append("This Job ID was saved before from a different sheet link. "
                        "Check that the Job ID is correct.")

    # 1. Rows -> people -> students.
    people, payload_conflicts, skipped = group_records(run.candidates)
    if skipped:
        warnings.append(f"{skipped} row(s) had no mobile, email or user id and were skipped.")
    resolver = StudentResolver(db, run_at, now)
    resolver.load(people)
    person_ids = [resolver.resolve(p) for p in people]
    try:
        counts = resolver.flush()
    except DuplicateKeyError as exc:
        raise IdentityClash(f"A student key was written by another process: {exc}") from exc

    # 2. One application per student for this job (two people can land on one student).
    apps: dict[str, dict] = {}
    for p, sid in zip(people, person_ids):
        sid = resolver.final_id(sid)
        a = apps.get(sid)
        if a is None:
            apps[sid] = {"stages": dict(p.stages), "category": p.category, "product": p.product,
                         "bucket": p.bucket, "tr_cleared": p.tr_cleared}
        else:
            for s in STAGES:
                a["stages"][s] = better_label(a["stages"][s], p.stages[s])
            if better_category(a["category"], p.category) != a["category"]:
                a["category"], a["product"] = p.category, p.product
            a["bucket"] = a["bucket"] or p.bucket
            a["tr_cleared"] = a["tr_cleared"] or p.tr_cleared

    if is_newest:
        ops = [ReplaceOne({"_id": f"{jkey}:{sid}"}, {
            "_id": f"{jkey}:{sid}", "job_key": jkey, "job_id": run.job_id, "student_id": sid,
            "stages": a["stages"], "furthest_stage": furthest_stage(a["stages"]),
            "category_at_run": a["category"], "product_at_run": a["product"],
            "bucket_at_run": a["bucket"], "tr_cleared_at_run": a["tr_cleared"],
            "run_id": run.run_id, "run_at": run_at, "updated_at": now,
        }, upsert=True) for sid, a in apps.items()]
        for i in range(0, len(ops), 1000):
            db.applications.bulk_write(ops[i:i + 1000], ordered=False)
        # Students who were in the old run of this job but not in this one.
        removed = db.applications.delete_many({"job_key": jkey, "run_id": {"$ne": run.run_id}}).deleted_count
    else:
        removed = 0

    # 3. Conflicts (each one is stored once and counted every time it shows up again).
    all_conflicts = {c.id: c for c in list(payload_conflicts) + list(resolver.conflicts)}
    _record_conflicts(db, all_conflicts.values(), run.job_id, now)

    summary = {
        "rows_received": len(run.candidates), "rows_skipped": skipped, "people_in_run": len(people),
        **counts, "applications": len(apps) if is_newest else 0,
        "applications_removed": removed, "identity_conflicts": len(all_conflicts),
    }

    # 4. Stats snapshot. Its _id is the run_id, so it is written last: if anything above
    #    failed, sending the same run again simply redoes the save.
    company = (run.company or (job or {}).get("company") or None)
    role = (run.role or (job or {}).get("role") or None)
    db.job_stats.insert_one({
        "_id": run.run_id, "job_key": jkey, "job_id": run.job_id, "company": company, "role": role,
        "sheet_url": run.sheet_url, "sheet_title": run.sheet_title, "tr_rule": run.tr_rule,
        "run_at": run_at, "saved_at": now, "is_latest": is_newest,
        "stages": {s: run.stages[s].model_dump() for s in STAGES},
        "save_summary": summary,
    })
    if is_newest:
        db.job_stats.update_many({"job_key": jkey, "_id": {"$ne": run.run_id}, "is_latest": True},
                                 {"$set": {"is_latest": False}})

    # 5. Job document.
    job_set = {"job_id": run.job_id, "updated_at": now}
    if is_newest:
        job_set.update(latest_run_id=run.run_id, latest_run_at=run_at, sheet_title=run.sheet_title,
                       sheet_url=run.sheet_url)
    if run.company:
        job_set["company"] = run.company
    if run.role:
        job_set["role"] = run.role
    job_update = {"$set": job_set, "$setOnInsert": {"created_at": now}, "$inc": {"run_count": 1}}
    if run.sheet_url:
        job_update["$addToSet"] = {"sheet_urls": run.sheet_url}
    db.jobs.update_one({"_id": jkey}, job_update, upsert=True)

    return {"status": "saved", "run_id": run.run_id, "job_id": run.job_id, "is_latest": is_newest,
            **summary, "warnings": warnings}


def _record_conflicts(db, conflicts, job_id: str, now) -> None:
    ops = []
    for c in conflicts:
        mobiles = [m for m in c.mobiles if m]
        ops.append(UpdateOne({"_id": c.id}, {
            "$setOnInsert": {"key_type": c.key_type, "key": c.key, "mobiles": mobiles,
                             "first_seen": now, "resolved": False},
            "$set": {"last_seen": now},
            "$addToSet": {"job_ids": job_id},
            "$inc": {"seen_count": 1},
        }, upsert=True))
    if ops:
        db.identity_conflicts.bulk_write(ops, ordered=False)


__all__ = ["save_run", "SaveBusy", "RunMismatch", "IdentityClash", "Conflict"]
