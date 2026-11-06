"""Hand edits to students (with history) and manual merges."""
from __future__ import annotations

import time

from pymongo.errors import DuplicateKeyError

from .identity import PROFILE_FIELDS, move_applications
from .normalize import clean_text, norm_bucket, norm_email, norm_mobile, norm_user_id, now_utc
from .service import SaveBusy, acquire_lock, release_lock

CATEGORIES = ("Academy", "Intensive", "External")


class EditError(ValueError):
    pass


def _with_lock(db, fn):
    """Edits wait for a running save (max ~20 s) so they never overwrite each other."""
    for _ in range(10):
        try:
            token = acquire_lock(db, now_utc())
            break
        except SaveBusy:
            time.sleep(2)
    else:
        raise SaveBusy("A save is running. Try again in a minute.")
    try:
        return fn()
    finally:
        release_lock(db, token)


def edit_student(db, sid: str, changes: dict, user: dict) -> dict:
    """changes may hold: name, product, category, bucket, tr_cleared, mobile,
    add_emails, remove_emails, add_user_ids, remove_user_ids, unlock (list of fields), note."""
    return _with_lock(db, lambda: _edit(db, sid, changes, user))


def _edit(db, sid: str, changes: dict, user: dict) -> dict:
    s = db.students.find_one({"_id": sid})
    if not s:
        raise LookupError("Student not found.")
    now = now_utc()
    sets, log, locked = {}, {}, set(s.get("locked_fields", []))

    # Profile fields: a hand edit locks the field.
    for f in PROFILE_FIELDS:
        if f not in changes or changes[f] is None and f != "bucket":
            continue
        v = changes[f]
        if f == "name":
            v = clean_text(v)
            if not v:
                raise EditError("Name can't be empty.")
        elif f == "product":
            v = clean_text(v)
        elif f == "category":
            if v not in CATEGORIES:
                raise EditError(f"Category must be one of {', '.join(CATEGORIES)}.")
        elif f == "bucket":
            v = norm_bucket(v)
        elif f == "tr_cleared":
            v = bool(v)
        if s.get(f) != v:
            sets[f] = v
            log[f] = {"from": s.get(f), "to": v}
        locked.add(f)

    # Unlock: the next sheet save may update the field again.
    for f in changes.get("unlock") or []:
        if f in locked and f not in sets:
            locked.discard(f)
            log.setdefault("unlocked", {"from": None, "to": []})["to"].append(f)

    # Identities.
    if changes.get("mobile") is not None:
        m = norm_mobile(changes["mobile"])
        if not m:
            raise EditError("Enter a 10-digit mobile number.")
        other = db.students.find_one({"mobile": m, "_id": {"$ne": sid}})
        if other:
            raise EditError(f"Mobile {m} belongs to another student ({other.get('name') or other['_id']}). "
                            "Merge the two students instead.")
        if m != s.get("mobile"):
            sets["mobile"] = m
            log["mobile"] = {"from": s.get("mobile"), "to": m}

    emails, uids = list(s.get("emails", [])), list(s.get("user_ids", []))
    for raw in changes.get("add_emails") or []:
        e = norm_email(raw)
        if not e:
            raise EditError(f"'{raw}' is not a valid email.")
        other = db.students.find_one({"emails": e, "_id": {"$ne": sid}})
        if other:
            raise EditError(f"{e} belongs to another student ({other.get('name') or other['_id']}).")
        if e not in emails:
            emails.append(e)
    for raw in changes.get("add_user_ids") or []:
        u = norm_user_id(raw)
        if not u:
            raise EditError(f"'{raw}' is not a valid user id.")
        other = db.students.find_one({"user_ids": u, "_id": {"$ne": sid}})
        if other:
            raise EditError(f"User id {u} belongs to another student ({other.get('name') or other['_id']}).")
        if u not in uids:
            uids.append(u)
    rm_e = {norm_email(x) for x in changes.get("remove_emails") or []}
    rm_u = {norm_user_id(x) for x in changes.get("remove_user_ids") or []}
    emails = [e for e in emails if e not in rm_e]
    uids = [u for u in uids if u not in rm_u]
    if not (sets.get("mobile") or s.get("mobile") or emails or uids):
        raise EditError("A student needs at least one mobile, email or user id.")

    update: dict = {"$set": {**sets, "updated_at": now, "locked_fields": sorted(locked)}}
    unset = {}
    if emails != list(s.get("emails", [])):
        log["emails"] = {"from": s.get("emails", []), "to": emails}
        if emails:
            update["$set"]["emails"] = sorted(emails)
        else:
            unset["emails"] = ""
    if uids != list(s.get("user_ids", [])):
        log["user_ids"] = {"from": s.get("user_ids", []), "to": uids}
        if uids:
            update["$set"]["user_ids"] = sorted(uids)
        else:
            unset["user_ids"] = ""
    if unset:
        update["$unset"] = unset
    if not log:
        return {"changed": False}
    try:
        db.students.update_one({"_id": sid}, update)
    except DuplicateKeyError:
        raise EditError("One of these numbers / emails was just added to another student. Reload and try again.")
    db.student_edits.insert_one({"student_id": sid, "by": user["_id"], "at": now, "changes": log,
                                 "note": clean_text(changes.get("note"))})
    return {"changed": True, "changes": log}


def merge_students(db, survivor_id: str, other_id: str, user: dict) -> dict:
    return _with_lock(db, lambda: _merge(db, survivor_id, other_id, user))


def _merge(db, survivor_id: str, other_id: str, user: dict) -> dict:
    if survivor_id == other_id:
        raise EditError("Pick two different students.")
    su, lo = db.students.find_one({"_id": survivor_id}), db.students.find_one({"_id": other_id})
    if not su or not lo:
        raise LookupError("Student not found.")
    if su.get("mobile") and lo.get("mobile") and su["mobile"] != lo["mobile"]:
        raise EditError("These students have different mobile numbers. Edit one of them first "
                        "(a student keeps one mobile number).")
    now = now_utc()
    db.student_merges.replace_one({"_id": other_id}, {"_id": other_id, "merged_into": survivor_id,
                                                      "merged_at": now, "merged_by": user["_id"], "student": lo},
                                  upsert=True)
    move_applications(db, other_id, survivor_id, now)
    db.students.delete_one({"_id": other_id})
    sets = {"updated_at": now}
    if lo.get("mobile") and not su.get("mobile"):
        sets["mobile"] = lo["mobile"]
    for f in PROFILE_FIELDS:
        if su.get(f) in (None, "") and lo.get(f) not in (None, ""):
            sets[f] = lo[f]
    add = {f: {"$each": lo[f]} for f in ("emails", "user_ids", "locked_fields") if lo.get(f)}
    add["merged_from"] = {"$each": [other_id] + list(lo.get("merged_from", []))}
    db.students.update_one({"_id": survivor_id}, {"$set": sets, "$addToSet": add})
    db.student_edits.insert_one({"student_id": survivor_id, "by": user["_id"], "at": now,
                                 "changes": {"merged": {"from": other_id, "to": survivor_id}}, "note": None})
    return {"merged": other_id, "into": survivor_id}


def edit_history(db, sid: str, limit: int = 50) -> list[dict]:
    out = []
    for e in db.student_edits.find({"student_id": sid}).sort("at", -1).limit(limit):
        e["id"] = str(e.pop("_id"))
        out.append(e)
    return out
