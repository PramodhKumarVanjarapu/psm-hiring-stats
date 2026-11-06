from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from .. import queries
from ..auth import admin, editor, viewer
from ..db import get_db
from ..schemas import JobPatch, RunIn
from ..service import IdentityClash, RunMismatch, SaveBusy, save_run

router = APIRouter(prefix="/api/v1", tags=["jobs"])
Stage = Literal["TA", "RS", "SC", "AS", "SP"]
Category = Literal["Academy", "Intensive", "External"]


@router.post("/runs", dependencies=[Depends(editor)])
def create_run(run: RunIn):
    """Save a run computed elsewhere (scripts). The React app uses /analyses instead."""
    try:
        return save_run(get_db(), run)
    except (SaveBusy, RunMismatch) as exc:
        raise HTTPException(409, str(exc))
    except IdentityClash as exc:
        raise HTTPException(409, f"{exc}. Please try saving again.")


@router.get("/jobs", dependencies=[Depends(viewer)])
def jobs(company: Optional[str] = None, search: Optional[str] = None,
         limit: int = Query(50, ge=1, le=500), skip: int = Query(0, ge=0)):
    return queries.list_jobs(get_db(), company, search, limit, skip)


@router.get("/jobs/{job_id}", dependencies=[Depends(viewer)])
def job(job_id: str):
    out = queries.get_job(get_db(), job_id)
    if not out:
        raise HTTPException(404, "Job not found.")
    return out


@router.patch("/jobs/{job_id}", dependencies=[Depends(editor)])
def patch_job(job_id: str, body: JobPatch):
    out = queries.update_job(get_db(), job_id, body.company, body.role)
    if not out:
        raise HTTPException(404, "Job not found.")
    return out


@router.delete("/jobs/{job_id}", dependencies=[Depends(admin)])
def remove_job(job_id: str, confirm: bool = False):
    if not confirm:
        raise HTTPException(400, "Add ?confirm=true to delete this job, its history and its applications.")
    out = queries.delete_job(get_db(), job_id)
    if not out:
        raise HTTPException(404, "Job not found.")
    return out


@router.get("/jobs/{job_id}/runs", dependencies=[Depends(viewer)])
def runs(job_id: str):
    return queries.job_runs(get_db(), job_id)


def _filters(stage, label, category, bucket, furthest_stage, q):
    if label and not stage:
        raise HTTPException(400, "label needs a stage, e.g. ?stage=RS&label=P1")
    return {"stage": stage, "label": label, "category": category, "bucket": bucket,
            "furthest": furthest_stage, "q": q}


@router.get("/jobs/{job_id}/candidates", dependencies=[Depends(viewer)])
def candidates(job_id: str, stage: Optional[Stage] = None, label: Optional[str] = None,
               category: Optional[Category] = None, bucket: Optional[str] = None,
               furthest_stage: Optional[Stage] = None, q: Optional[str] = None,
               limit: int = Query(100, ge=1, le=5000), skip: int = Query(0, ge=0)):
    f = _filters(stage, label, category, bucket, furthest_stage, q)
    return queries.job_candidates(get_db(), job_id, limit=limit, skip=skip, **f)


@router.get("/jobs/{job_id}/candidates.csv", dependencies=[Depends(viewer)])
def candidates_csv(job_id: str, stage: Optional[Stage] = None, label: Optional[str] = None,
                   category: Optional[Category] = None, bucket: Optional[str] = None,
                   furthest_stage: Optional[Stage] = None, q: Optional[str] = None):
    f = _filters(stage, label, category, bucket, furthest_stage, q)
    text = queries.candidates_csv(get_db(), job_id, **f)
    name = f"{job_id.strip().replace(' ', '_')}_candidates.csv"
    return Response(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
