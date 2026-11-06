"""Read-side queries used by the API."""
from __future__ import annotations

import re

from .normalize import STAGES, job_key, norm_email, norm_mobile, norm_user_id, now_utc

BUCKETS = ("A", "B", "C", "D")


def _latest_stats(db, jkey: str):
    return db.job_stats.find_one({"job_key": jkey}, sort=[("run_at", -1)])


def _stage_counts(stats: dict | None) -> dict:
    stages = (stats or {}).get("stages", {})
    return {s: stages.get(s, {}).get("unique", 0) for s in STAGES}


# ---- jobs ---------------------------------------------------------------- #
def list_jobs(db, company: str | None, search: str | None, limit: int, skip: int) -> dict:
    flt: dict = {}
    if company:
        flt["company"] = {"$regex": f"^{re.escape(company.strip())}$", "$options": "i"}
    if search:
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        flt["$or"] = [{"job_id": rx}, {"company": rx}, {"role": rx}, {"sheet_title": rx}]
    total = db.jobs.count_documents(flt)
    jobs = list(db.jobs.find(flt).sort("updated_at", -1).skip(skip).limit(limit))
    run_ids = [j.get("latest_run_id") for j in jobs if j.get("latest_run_id")]
    stats = {d["_id"]: d for d in db.job_stats.find({"_id": {"$in": run_ids}}, {"stages": 1})}
    items = []
    for j in jobs:
        items.append({**_job_out(j), "stage_counts": _stage_counts(stats.get(j.get("latest_run_id")))})
    return {"total": total, "items": items}


def _job_out(j: dict) -> dict:
    return {"job_id": j.get("job_id"), "job_key": j["_id"], "company": j.get("company"),
            "role": j.get("role"), "sheet_title": j.get("sheet_title"), "sheet_url": j.get("sheet_url"),
            "sheet_urls": j.get("sheet_urls", []), "run_count": j.get("run_count", 0),
            "latest_run_id": j.get("latest_run_id"), "latest_run_at": j.get("latest_run_at"),
            "created_at": j.get("created_at"), "updated_at": j.get("updated_at")}


def get_job(db, job_id: str) -> dict | None:
    jkey = job_key(job_id)
    j = db.jobs.find_one({"_id": jkey})
    if not j:
        return None
    stats = _latest_stats(db, jkey)
    return {**_job_out(j), "latest_stats": _stats_out(stats) if stats else None}


def _stats_out(d: dict) -> dict:
    return {"run_id": d["_id"], "job_id": d["job_id"], "company": d.get("company"), "role": d.get("role"),
            "run_at": d.get("run_at"), "saved_at": d.get("saved_at"), "is_latest": d.get("is_latest"),
            "sheet_url": d.get("sheet_url"), "sheet_title": d.get("sheet_title"),
            "tr_rule": d.get("tr_rule"), "stages": d.get("stages", {}),
            "save_summary": d.get("save_summary", {})}


def job_runs(db, job_id: str) -> list[dict]:
    return [_stats_out(d) for d in db.job_stats.find({"job_key": job_key(job_id)}).sort("run_at", -1)]


def update_job(db, job_id: str, company: str | None, role: str | None) -> dict | None:
    jkey = job_key(job_id)
    fields = {k: v.strip() for k, v in (("company", company), ("role", role)) if v and v.strip()}
    if not db.jobs.find_one({"_id": jkey}):
        return None
    if fields:
        db.jobs.update_one({"_id": jkey}, {"$set": {**fields, "updated_at": now_utc()}})
        db.job_stats.update_many({"job_key": jkey}, {"$set": fields})
    return get_job(db, job_id)


def delete_job(db, job_id: str) -> dict | None:
    """Remove a job, its stats history and its applications. Students are kept."""
    jkey = job_key(job_id)
    if not db.jobs.find_one({"_id": jkey}):
        return None
    return {
        "job_id": job_id,
        "runs_deleted": db.job_stats.delete_many({"job_key": jkey}).deleted_count,
        "applications_deleted": db.applications.delete_many({"job_key": jkey}).deleted_count,
        "job_deleted": db.jobs.delete_one({"_id": jkey}).deleted_count,
    }


# ---- candidates of a job -------------------------------------------------- #
def job_candidates(db, job_id: str, stage: str | None = None, label: str | None = None,
                   category: str | None = None, bucket: str | None = None, furthest: str | None = None,
                   limit: int = 100, skip: int = 0, q: str | None = None) -> dict:
    match: dict = {"job_key": job_key(job_id)}
    if stage:
        match[f"stages.{stage}"] = {"$ne": None} if not label else label
    if category:
        match["category_at_run"] = category
    if bucket:
        match["bucket_at_run"] = bucket.upper()
    if furthest:
        match["furthest_stage"] = furthest
    if q and q.strip():
        found = list_students(db, q, None, None, None, limit=5000, skip=0)["items"]
        match["student_id"] = {"$in": [f["student_id"] for f in found]}
    total = db.applications.count_documents(match)
    apps = list(db.applications.find(match).sort("_id", 1).skip(skip).limit(limit))
    students = {s["_id"]: s for s in db.students.find({"_id": {"$in": [a["student_id"] for a in apps]}})}
    items = []
    for a in apps:
        s = students.get(a["student_id"], {})
        items.append({
            "student_id": a["student_id"], "name": s.get("name"), "mobile": s.get("mobile"),
            "emails": s.get("emails", []), "user_ids": s.get("user_ids", []),
            "stages": a.get("stages", {}), "furthest_stage": a.get("furthest_stage"),
            "category": a.get("category_at_run"), "product": a.get("product_at_run"),
            "bucket": a.get("bucket_at_run"), "tr_cleared": a.get("tr_cleared_at_run"),
        })
    return {"total": total, "items": items}


# ---- one student ------------------------------------------------------------ #
def find_student(db, mobile: str | None, email: str | None, user_id: str | None,
                 student_id: str | None) -> dict | None:
    flt = None
    if student_id:
        # Follow merges, so an old student id still finds the person.
        for _ in range(10):
            merged = db.student_merges.find_one({"_id": student_id})
            if not merged:
                break
            student_id = merged["merged_into"]
        flt = {"_id": student_id}
    elif norm_mobile(mobile):
        flt = {"mobile": norm_mobile(mobile)}
    elif norm_user_id(user_id):
        flt = {"user_ids": norm_user_id(user_id)}
    elif norm_email(email):
        flt = {"emails": norm_email(email)}
    if flt is None:
        return None
    s = db.students.find_one(flt)
    if not s:
        return None
    apps = list(db.applications.find({"student_id": s["_id"]}).sort("run_at", -1))
    jobs = {j["_id"]: j for j in db.jobs.find({"_id": {"$in": [a["job_key"] for a in apps]}})}
    return {
        "student_id": s["_id"], "name": s.get("name"), "mobile": s.get("mobile"),
        "emails": s.get("emails", []), "user_ids": s.get("user_ids", []),
        "product": s.get("product"), "category": s.get("category"), "bucket": s.get("bucket"),
        "tr_cleared": s.get("tr_cleared"), "profile_as_of": s.get("profile_as_of"),
        "merged_from": s.get("merged_from", []), "locked_fields": s.get("locked_fields", []),
        "created_at": s.get("created_at"), "updated_at": s.get("updated_at"),
        "applications": [{
            "job_id": a["job_id"], "company": jobs.get(a["job_key"], {}).get("company"),
            "role": jobs.get(a["job_key"], {}).get("role"), "stages": a.get("stages", {}),
            "furthest_stage": a.get("furthest_stage"), "category": a.get("category_at_run"),
            "bucket": a.get("bucket_at_run"), "tr_cleared": a.get("tr_cleared_at_run"),
            "run_at": a.get("run_at"),
        } for a in apps],
    }


# ---- reports ------------------------------------------------------------- #
def _latest_runs(db, company: str | None) -> list[dict]:
    flt: dict = {"is_latest": True}
    if company:
        flt["company"] = {"$regex": f"^{re.escape(company.strip())}$", "$options": "i"}
    return list(db.job_stats.find(flt).sort("run_at", -1))


def funnel_report(db, company: str | None) -> dict:
    rows, totals = [], {s: 0 for s in STAGES}
    for d in _latest_runs(db, company):
        c = _stage_counts(d)
        for s in STAGES:
            totals[s] += c[s]
        rows.append({"job_id": d["job_id"], "company": d.get("company"), "role": d.get("role"),
                     "run_at": d.get("run_at"), **c,
                     "sp_pct_of_ta": round(100 * c["SP"] / c["TA"], 1) if c["TA"] else 0.0})
    totals["sp_pct_of_ta"] = round(100 * totals["SP"] / totals["TA"], 1) if totals["TA"] else 0.0
    return {"jobs": rows, "totals": totals}


def bucket_report(db, company: str | None) -> dict:
    """Academy bucket counts per stage, added up over the latest run of every job."""
    out = {b: {s: 0 for s in STAGES} for b in BUCKETS}
    runs = _latest_runs(db, company)
    for d in runs:
        for s in STAGES:
            buckets = d.get("stages", {}).get(s, {}).get("buckets", {})
            for b in BUCKETS:
                out[b][s] += int(buckets.get(b, {}).get("candidates", 0))
    rows = [{"bucket": b, **out[b],
             "sp_pct_of_ta": round(100 * out[b]["SP"] / out[b]["TA"], 1) if out[b]["TA"] else 0.0}
            for b in BUCKETS]
    return {"jobs_counted": len(runs), "buckets": rows}


def list_conflicts(db, resolved: bool, limit: int, skip: int) -> dict:
    flt = {"resolved": resolved}
    total = db.identity_conflicts.count_documents(flt)
    items = []
    for c in db.identity_conflicts.find(flt).sort("last_seen", -1).skip(skip).limit(limit):
        c["id"] = c.pop("_id")
        items.append(c)
    return {"total": total, "items": items}


def resolve_conflict(db, conflict_id: str) -> bool:
    r = db.identity_conflicts.update_one({"_id": conflict_id},
                                         {"$set": {"resolved": True, "resolved_at": now_utc()}})
    return r.matched_count == 1


# ---- students list -------------------------------------------------------------- #
def list_students(db, q: str | None, category: str | None, bucket: str | None, locked: bool | None,
                  limit: int, skip: int) -> dict:
    flt: dict = {}
    if q and q.strip():
        q = q.strip()
        ors = [{"name": {"$regex": re.escape(q), "$options": "i"}}]
        if norm_mobile(q):
            ors.append({"mobile": norm_mobile(q)})
        elif re.fullmatch(r"\d{3,}", q):
            ors.append({"mobile": {"$regex": "^" + re.escape(q)}})
        ors.append({"emails": {"$regex": "^" + re.escape(q.lower())}})
        ors.append({"user_ids": {"$regex": "^" + re.escape(q.lower().replace(" ", ""))}})
        flt["$or"] = ors
    if category:
        flt["category"] = category
    if bucket:
        flt["bucket"] = bucket.upper()
    if locked is not None:
        flt["locked_fields.0"] = {"$exists": locked}
    total = db.students.count_documents(flt)
    docs = list(db.students.find(flt).sort([("updated_at", -1), ("_id", 1)]).skip(skip).limit(limit))
    ids = [d["_id"] for d in docs]
    counts = {sid: {"jobs": 0, "reached_sp": 0} for sid in ids}
    for a in db.applications.find({"student_id": {"$in": ids}}, {"student_id": 1, "stages.SP": 1}):
        c = counts[a["student_id"]]
        c["jobs"] += 1
        if a.get("stages", {}).get("SP") is not None:
            c["reached_sp"] += 1
    return {"total": total, "items": [{
        "student_id": d["_id"], "name": d.get("name"), "mobile": d.get("mobile"),
        "emails": d.get("emails", []), "user_ids": d.get("user_ids", []), "product": d.get("product"),
        "category": d.get("category"), "bucket": d.get("bucket"), "tr_cleared": d.get("tr_cleared"),
        "locked_fields": d.get("locked_fields", []), "updated_at": d.get("updated_at"), **counts[d["_id"]],
    } for d in docs]}


# ---- dashboard -------------------------------------------------------------------- #
def _sum_stages(runs: list[dict]) -> dict:
    tot = {s: 0 for s in STAGES}
    for d in runs:
        c = _stage_counts(d)
        for s in STAGES:
            tot[s] += c[s]
    return tot


def _pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def _category_split(runs: list[dict], stage: str) -> dict:
    out = {"academy": 0, "intensive": 0, "external": 0}
    for d in runs:
        st = d.get("stages", {}).get(stage, {})
        for k in out:
            out[k] += int(st.get(k, 0))
    return out


def dashboard(db) -> dict:
    runs = _latest_runs(db, None)
    totals = _sum_stages(runs)
    companies = company_list(db)["items"]
    # Only named companies with enough applications; best and lowest never share a company.
    ranked = [c for c in companies if c["company"] != UNASSIGNED and c["stages"]["TA"] >= 20]
    ranked.sort(key=lambda c: c["sp_pct_of_ta"], reverse=True)
    top = ranked[:5]
    bottom = [c for c in reversed(ranked) if c not in top][:5]
    by_month: dict = {}
    for d in runs:
        ra = d.get("run_at")
        if not ra:
            continue
        key = ra.strftime("%Y-%m")
        m = by_month.setdefault(key, {"month": key, "jobs": 0, **{s: 0 for s in STAGES}})
        m["jobs"] += 1
        for s, n in _stage_counts(d).items():
            m[s] += n
    recent = [{"job_id": d["job_id"], "company": d.get("company"), "role": d.get("role"),
               "run_at": d.get("run_at"), "TA": _stage_counts(d)["TA"], "SP": _stage_counts(d)["SP"]}
              for d in db.job_stats.find({}, {"stages": 1, "job_id": 1, "company": 1, "role": 1, "run_at": 1})
              .sort("saved_at", -1).limit(8)]
    return {
        "jobs": db.jobs.count_documents({}),
        "companies": len([c for c in companies if c["company"] != UNASSIGNED]),
        "students": db.students.count_documents({}),
        "open_conflicts": db.identity_conflicts.count_documents({"resolved": False}),
        "funnel": totals,
        "sp_pct_of_ta": _pct(totals["SP"], totals["TA"]),
        "category_ta": _category_split(runs, "TA"),
        "category_sp": _category_split(runs, "SP"),
        "top_companies": top,
        "bottom_companies": bottom,
        "by_month": sorted(by_month.values(), key=lambda m: m["month"])[-12:],
        "recent_saves": recent,
    }


# ---- companies ---------------------------------------------------------------------- #
UNASSIGNED = "Unassigned"


def _company_rows(runs: list[dict]) -> dict:
    groups: dict = {}
    for d in runs:
        name = d.get("company") or UNASSIGNED
        g = groups.setdefault(name, {"company": name, "jobs": 0, "stages": {s: 0 for s in STAGES},
                                     "category_ta": {"academy": 0, "intensive": 0, "external": 0},
                                     "category_sp": {"academy": 0, "intensive": 0, "external": 0},
                                     "buckets": {b: {s: 0 for s in STAGES} for b in BUCKETS},
                                     "last_run_at": None})
        g["jobs"] += 1
        for s, n in _stage_counts(d).items():
            g["stages"][s] += n
        for stage, key in (("TA", "category_ta"), ("SP", "category_sp")):
            for k, v in _category_split([d], stage).items():
                g[key][k] += v
        for s in STAGES:
            bk = d.get("stages", {}).get(s, {}).get("buckets", {})
            for b in BUCKETS:
                g["buckets"][b][s] += int(bk.get(b, {}).get("candidates", 0))
        ra = d.get("run_at")
        if ra and (g["last_run_at"] is None or ra > g["last_run_at"]):
            g["last_run_at"] = ra
    for g in groups.values():
        st = g["stages"]
        g["rs_pct_of_ta"] = _pct(st["RS"], st["TA"])
        g["sp_pct_of_ta"] = _pct(st["SP"], st["TA"])
        g["sp_pct_of_rs"] = _pct(st["SP"], st["RS"])
    return groups


def company_list(db) -> dict:
    groups = _company_rows(_latest_runs(db, None))
    items = sorted(groups.values(), key=lambda g: (g["company"] == UNASSIGNED, -g["stages"]["TA"]))
    return {"total": len(items), "items": items}


def company_detail(db, name: str) -> dict | None:
    flt = {"is_latest": True}
    flt["company"] = None if name == UNASSIGNED else {"$regex": f"^{re.escape(name)}$", "$options": "i"}
    runs = list(db.job_stats.find(flt).sort("run_at", -1))
    if not runs:
        return None
    g = _company_rows(runs)
    summary = next(iter(g.values()))
    summary["company"] = runs[0].get("company") or UNASSIGNED
    summary["job_list"] = [{"job_id": d["job_id"], "role": d.get("role"), "run_at": d.get("run_at"),
                            "stages": _stage_counts(d), "sp_pct_of_ta": _pct(_stage_counts(d)["SP"],
                                                                             _stage_counts(d)["TA"])}
                           for d in runs]
    return summary


# ---- CSV export --------------------------------------------------------------------- #
def candidates_csv(db, job_id: str, **filters) -> str:
    import csv
    import io
    data = job_candidates(db, job_id, limit=1_000_000, skip=0, **filters)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Name", "Mobile", "Emails", "User IDs", "Category", "Product", "Bucket", "TR cleared",
                *STAGES, "Furthest stage"])
    for c in data["items"]:
        w.writerow([c["name"] or "", c["mobile"] or "", "; ".join(c["emails"]), "; ".join(c["user_ids"]),
                    c["category"] or "", c["product"] or "", c["bucket"] or "",
                    "Yes" if c["tr_cleared"] else "No",
                    *[c["stages"].get(s) or "" for s in STAGES], c["furthest_stage"] or ""])
    return buf.getvalue()
