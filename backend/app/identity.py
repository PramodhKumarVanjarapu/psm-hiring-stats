"""Turning stage rows into people, and people into `students` documents.

Rules (same in both steps):
  * A person is identified by mobile, user id or email. Any shared one links two rows / students.
  * Mobile is the strongest key. Two different mobile numbers are NEVER merged, even if they
    share an email or user id. The shared email / user id stays with the first owner and the
    clash is logged in `identity_conflicts` for a human to check.
  * Students that turn out to be the same person (e.g. one saved with only an email, one with
    a mobile, now linked by a row that has both) are merged into the oldest one. The removed
    document is copied to `student_merges` first, so nothing is lost.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from datetime import datetime, timezone

from .normalize import (STAGES, TA_LABEL, as_utc, better_category, better_label, clean_text,
                        furthest_stage, norm_bucket, norm_email, norm_mobile, norm_user_id)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

Key = tuple[str, str]  # ("mobile" | "user_id" | "email", value)


@dataclass(frozen=True)
class Conflict:
    key_type: str
    key: str
    mobiles: tuple  # the two (or more) different mobiles that share this key

    @property
    def id(self) -> str:
        return f"{self.key_type}:{self.key}:{'|'.join(self.mobiles)}"


@dataclass
class Person:
    mobile: str | None = None
    emails: set = field(default_factory=set)
    user_ids: set = field(default_factory=set)
    name: str | None = None
    product: str | None = None
    category: str | None = None
    bucket: str | None = None
    tr_cleared: bool = False
    stages: dict = field(default_factory=lambda: {s: None for s in STAGES})
    rows: int = 0

    def keys(self) -> list[Key]:
        out: list[Key] = [("mobile", self.mobile)] if self.mobile else []
        out += [("user_id", u) for u in sorted(self.user_ids)]
        out += [("email", e) for e in sorted(self.emails)]
        return out

    def absorb(self, other: "Person") -> None:
        """Combine two entries of the same person (best value of each field wins)."""
        self.mobile = self.mobile or other.mobile
        self.emails |= other.emails
        self.user_ids |= other.user_ids
        self.name = self.name or other.name
        if better_category(self.category, other.category) != self.category:
            self.product, self.category = other.product, other.category
        self.product = self.product or other.product
        self.bucket = self.bucket or other.bucket
        self.tr_cleared = self.tr_cleared or other.tr_cleared
        for s in STAGES:
            self.stages[s] = better_label(self.stages[s], other.stages[s])
        self.rows += other.rows


# --------------------------------------------------------------------------- #
# Step 1: rows of this run -> people
# --------------------------------------------------------------------------- #
def group_records(records) -> tuple[list[Person], list[Conflict], int]:
    """Collapse every row (all stages, repeats included) into one Person per real person."""
    rows, skipped = [], 0
    for r in records:
        m, u, e = norm_mobile(r.mobile), norm_user_id(r.user_id), norm_email(r.email)
        if not (m or u or e):
            skipped += 1
            continue
        rows.append((r, m, u, e))

    parent = list(range(len(rows)))
    mob = [m for _, m, _, _ in rows]

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner: dict[Key, int] = {}
    dropped: dict[int, set] = {}
    conflicts: set[Conflict] = set()
    for i, (_, m, u, e) in enumerate(rows):
        for key in (("mobile", m), ("user_id", u), ("email", e)):
            if not key[1]:
                continue
            if key not in owner:
                owner[key] = i
                continue
            ri, rj = find(i), find(owner[key])
            if ri == rj:
                continue
            if mob[ri] and mob[rj] and mob[ri] != mob[rj]:
                conflicts.add(Conflict(key[0], key[1], tuple(sorted({mob[ri], mob[rj]}))))
                dropped.setdefault(i, set()).add(key)
                continue
            parent[ri] = rj
            mob[rj] = mob[rj] or mob[ri]

    people: dict[int, Person] = {}
    for i, (r, m, u, e) in enumerate(rows):
        drop = dropped.get(i, set())
        p = Person(
            mobile=m,
            emails={e} if e and ("email", e) not in drop else set(),
            user_ids={u} if u and ("user_id", u) not in drop else set(),
            name=clean_text(r.name),
            product=clean_text(r.product),
            category=r.category or "External",
            bucket=norm_bucket(r.bucket),
            tr_cleared=bool(r.tr_cleared),
            rows=1,
        )
        p.stages[r.stage] = TA_LABEL if r.stage == "TA" else (clean_text(r.label) or "Other / blank")
        root = find(i)
        if root in people:
            people[root].absorb(p)
        else:
            people[root] = p
    return list(people.values()), sorted(conflicts, key=lambda c: c.id), skipped


# --------------------------------------------------------------------------- #
# Step 2: people -> students collection
# --------------------------------------------------------------------------- #
PROFILE_FIELDS = ("name", "product", "category", "bucket", "tr_cleared")


def new_student_id() -> str:
    return "stu_" + secrets.token_hex(8)


class StudentResolver:
    """Works on an in-memory copy of the matching students, then writes once (flush)."""

    def __init__(self, db, run_at, now):
        self.db, self.run_at, self.now = db, as_utc(run_at), now
        self.docs: dict[str, dict] = {}       # current state, by student id
        self.original: dict[str, dict] = {}   # as loaded from the database
        self.by_key: dict[Key, str] = {}
        self.new_ids: set[str] = set()
        self.touched: set[str] = set()
        self.alias: dict[str, str] = {}       # merged id -> surviving id
        self.merged_in_db: list[tuple[str, str]] = []
        self.conflicts: set[Conflict] = set()

    # ---- loading -------------------------------------------------------- #
    def load(self, people: list[Person]) -> None:
        mobiles = sorted({p.mobile for p in people if p.mobile})
        emails = sorted({e for p in people for e in p.emails})
        uids = sorted({u for p in people for u in p.user_ids})
        for field_name, values in (("mobile", mobiles), ("emails", emails), ("user_ids", uids)):
            for i in range(0, len(values), 5000):
                for doc in self.db.students.find({field_name: {"$in": values[i:i + 5000]}}):
                    if doc["_id"] not in self.docs:
                        self.docs[doc["_id"]] = doc
                        self.original[doc["_id"]] = {**doc, "emails": list(doc.get("emails", [])),
                                                     "user_ids": list(doc.get("user_ids", []))}
                        self._index(doc["_id"])

    def _index(self, sid: str) -> None:
        d = self.docs[sid]
        if d.get("mobile"):
            self.by_key[("mobile", d["mobile"])] = sid
        for u in d.get("user_ids", []):
            self.by_key[("user_id", u)] = sid
        for e in d.get("emails", []):
            self.by_key[("email", e)] = sid

    def final_id(self, sid: str) -> str:
        while sid in self.alias:
            sid = self.alias[sid]
        return sid

    # ---- matching ------------------------------------------------------- #
    def resolve(self, p: Person) -> str:
        """Return the student id for this person, creating / merging students as needed."""
        matched: list[str] = []
        for k in p.keys():  # mobile first, then user ids, then emails
            sid = self.by_key.get(k)
            if sid and sid not in matched:
                matched.append(sid)

        target_mobile = p.mobile or next(
            (self.docs[s]["mobile"] for s in matched if self.docs[s].get("mobile")), None)
        compatible = [s for s in matched if self.docs[s].get("mobile") in (None, target_mobile)]
        clashing = [s for s in matched if s not in compatible]

        # Keys already owned by a student with a DIFFERENT mobile stay with that student.
        drop = {k for k in p.keys() if self.by_key.get(k) in clashing}
        for k in drop:
            other = self.docs[self.by_key[k]].get("mobile")
            self.conflicts.add(Conflict(k[0], k[1], tuple(sorted({other, target_mobile}))))

        if compatible:
            survivor = min(compatible, key=lambda s: (self._created(s), s))
            for loser in compatible:
                if loser != survivor:
                    self._merge(loser, survivor)
        else:
            survivor = new_student_id()
            self.docs[survivor] = {"_id": survivor, "created_at": self.now, "emails": [], "user_ids": [],
                                   "merged_from": [], "tr_cleared": False}
            self.new_ids.add(survivor)

        self._apply(survivor, p, drop)
        return survivor

    def _created(self, sid: str):
        return as_utc(self.docs[sid].get("created_at")) or self.now

    def _merge(self, loser: str, survivor: str) -> None:
        lo, su = self.docs.pop(loser), self.docs[survivor]
        su["mobile"] = su.get("mobile") or lo.get("mobile")
        su["emails"] = sorted(set(su.get("emails", [])) | set(lo.get("emails", [])))
        su["user_ids"] = sorted(set(su.get("user_ids", [])) | set(lo.get("user_ids", [])))
        su["merged_from"] = sorted(set(su.get("merged_from", [])) | set(lo.get("merged_from", []))
                                   | ({loser} if loser not in self.new_ids else set()))
        # Keep the newer profile; fill gaps from the other one.
        lo_asof = as_utc(lo.get("profile_as_of")) or _EPOCH
        su_asof = as_utc(su.get("profile_as_of")) or _EPOCH
        newer, older = (lo, su) if lo_asof > su_asof else (su, lo)
        su_locked, lo_locked = set(su.get("locked_fields", [])), set(lo.get("locked_fields", []))
        for f in PROFILE_FIELDS:
            if f in su_locked:
                continue                      # a hand-edited value always wins
            if f in lo_locked:
                su[f] = lo.get(f)
                continue
            su[f] = newer.get(f) if newer.get(f) not in (None, "") else older.get(f)
        su["locked_fields"] = sorted(su_locked | lo_locked)
        su["profile_as_of"] = newer.get("profile_as_of") or older.get("profile_as_of")
        su["tr_cleared"] = bool(su.get("tr_cleared"))

        self.alias[loser] = survivor
        if loser in self.new_ids:
            self.new_ids.discard(loser)
        else:
            self.merged_in_db.append((loser, survivor))
        self.touched.discard(loser)
        self.touched.add(survivor)
        for k, v in list(self.by_key.items()):
            if v == loser:
                self.by_key[k] = survivor

    def _apply(self, sid: str, p: Person, drop: set) -> None:
        d = self.docs[sid]
        if p.mobile and ("mobile", p.mobile) not in drop and not d.get("mobile"):
            d["mobile"] = p.mobile
        d["emails"] = sorted(set(d.get("emails", [])) | {e for e in p.emails if ("email", e) not in drop})
        d["user_ids"] = sorted(set(d.get("user_ids", [])) | {u for u in p.user_ids if ("user_id", u) not in drop})

        locked = set(d.get("locked_fields", []))   # fields edited by hand are never overwritten
        incoming = {f: v for f, v in {"name": p.name, "product": p.product, "category": p.category,
                                      "bucket": p.bucket, "tr_cleared": p.tr_cleared}.items()
                    if f not in locked}
        as_of = as_utc(d.get("profile_as_of"))
        if as_of is None or self.run_at >= as_of:
            # This run is the newest information about the student: it becomes the profile
            # (a blank name never overwrites a known one).
            for f, v in incoming.items():
                if f == "name" and not v:
                    continue
                d[f] = v
            d["profile_as_of"] = self.run_at
        else:
            # Older run (saved late): only fill fields that are still empty.
            for f, v in incoming.items():
                if d.get(f) in (None, "") and v not in (None, ""):
                    d[f] = v
        self.touched.add(sid)
        self._index(sid)

    # ---- writing -------------------------------------------------------- #
    def flush(self) -> dict:
        db, now = self.db, self.now
        merged = 0
        # 1. Merged students: keep a copy, move their applications, then delete them.
        for loser, _ in self.merged_in_db:
            survivor = self.final_id(loser)
            original = self.original.get(loser) or db.students.find_one({"_id": loser})
            if original is None:
                continue
            db.student_merges.replace_one(
                {"_id": loser},
                {"_id": loser, "merged_into": survivor, "merged_at": now, "student": original},
                upsert=True)
            move_applications(db, loser, survivor, now)
            db.students.delete_one({"_id": loser})
            merged += 1

        # 2. Existing students that changed.
        updated = 0
        for sid in sorted(self.touched - self.new_ids):
            if sid in self.alias or sid not in self.docs:
                continue
            d = self.docs[sid]
            set_fields = {f: d.get(f) for f in PROFILE_FIELDS}
            set_fields.update(profile_as_of=d.get("profile_as_of"), updated_at=now)
            if d.get("mobile"):
                set_fields["mobile"] = d["mobile"]
            update = {"$set": set_fields}
            add = {f: {"$each": d[f]} for f in ("emails", "user_ids", "merged_from", "locked_fields")
                   if d.get(f)}
            if add:
                update["$addToSet"] = add
            db.students.update_one({"_id": sid}, update)
            updated += 1

        # 3. New students.
        new_docs = []
        for sid in sorted(self.new_ids):
            d = {k: v for k, v in self.docs[sid].items() if v not in ([], None) or k in PROFILE_FIELDS}
            d["updated_at"] = now
            new_docs.append(d)
        if new_docs:
            db.students.insert_many(new_docs, ordered=True)
        return {"students_created": len(new_docs), "students_updated": updated, "students_merged": merged}


def move_applications(db, loser: str, survivor: str, now) -> None:
    """Point a merged student's applications at the surviving student (combining duplicates)."""
    for app in list(db.applications.find({"student_id": loser})):
        target_id = f"{app['job_key']}:{survivor}"
        existing = db.applications.find_one({"_id": target_id})
        if existing:
            stages = {s: better_label(existing["stages"].get(s), app["stages"].get(s)) for s in STAGES}
            db.applications.update_one({"_id": target_id}, {"$set": {
                "stages": stages, "furthest_stage": furthest_stage(stages), "updated_at": now}})
        else:
            db.applications.insert_one({**app, "_id": target_id, "student_id": survivor, "updated_at": now})
        db.applications.delete_one({"_id": app["_id"]})
