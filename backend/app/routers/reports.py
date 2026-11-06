from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import queries
from ..auth import editor, viewer
from ..db import get_db

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/dashboard", dependencies=[Depends(viewer)])
def dashboard():
    return queries.dashboard(get_db())


@router.get("/companies", dependencies=[Depends(viewer)])
def companies():
    return queries.company_list(get_db())


@router.get("/companies/{name}", dependencies=[Depends(viewer)])
def company(name: str):
    out = queries.company_detail(get_db(), name)
    if not out:
        raise HTTPException(404, "Company not found.")
    return out


@router.get("/reports/funnel", dependencies=[Depends(viewer)])
def funnel(company: Optional[str] = None):
    return queries.funnel_report(get_db(), company)


@router.get("/reports/buckets", dependencies=[Depends(viewer)])
def buckets(company: Optional[str] = None):
    return queries.bucket_report(get_db(), company)


@router.get("/identity-conflicts", dependencies=[Depends(viewer)])
def conflicts(resolved: bool = False, limit: int = Query(100, ge=1, le=1000), skip: int = Query(0, ge=0)):
    db = get_db()
    out = queries.list_conflicts(db, resolved, limit, skip)
    # Attach the students involved so the page can offer "open" / "merge".
    for c in out["items"]:
        involved = []
        for m in c.get("mobiles", []):
            s = db.students.find_one({"mobile": m}, {"name": 1, "mobile": 1})
            if s:
                involved.append({"student_id": s["_id"], "name": s.get("name"), "mobile": m})
        field = {"email": "emails", "user_id": "user_ids"}.get(c.get("key_type"))
        if field:
            s = db.students.find_one({field: c["key"]}, {"name": 1, "mobile": 1})
            if s and s["_id"] not in [i["student_id"] for i in involved]:
                involved.append({"student_id": s["_id"], "name": s.get("name"), "mobile": s.get("mobile")})
        c["students"] = involved
    return out


@router.post("/identity-conflicts/{conflict_id:path}/resolve", dependencies=[Depends(editor)])
def resolve(conflict_id: str):
    if not queries.resolve_conflict(get_db(), conflict_id):
        raise HTTPException(404, "Conflict not found.")
    return {"id": conflict_id, "resolved": True}
