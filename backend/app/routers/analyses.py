from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ..analysis import runner
from ..analysis.sheets import service_account_email
from ..auth import editor, viewer
from ..db import get_db
from ..service import IdentityClash, RunMismatch, SaveBusy

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"])


class AnalysisIn(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    sheet_url: str = Field(min_length=10, max_length=1000)
    company: str | None = Field(default=None, max_length=200)
    role: str | None = Field(default=None, max_length=200)


@router.get("/setup", dependencies=[Depends(viewer)])
def setup():
    """What the New analysis page needs to show (who to share sheets with)."""
    return {"service_account_email": service_account_email()}


@router.post("")
def start(body: AnalysisIn, tasks: BackgroundTasks, user=Depends(editor)):
    db = get_db()
    try:
        a = runner.create_analysis(db, body.job_id, body.sheet_url, body.company, body.role, user)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    tasks.add_task(runner.run_analysis, db, a["id"])
    return a


@router.get("", dependencies=[Depends(viewer)])
def recent(limit: int = 20):
    return runner.list_analyses(get_db(), min(max(limit, 1), 100))


@router.get("/{aid}", dependencies=[Depends(viewer)])
def get(aid: str):
    a = runner.get_analysis(get_db(), aid)
    if not a:
        raise HTTPException(404, "Analysis not found (unsaved analyses are removed after 7 days).")
    return a


@router.post("/{aid}/save")
def save(aid: str, user=Depends(editor)):
    try:
        return runner.save_analysis(get_db(), aid, user)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except (SaveBusy, RunMismatch) as exc:
        raise HTTPException(409, str(exc))
    except IdentityClash as exc:
        raise HTTPException(409, f"{exc}. Please try saving again.")
