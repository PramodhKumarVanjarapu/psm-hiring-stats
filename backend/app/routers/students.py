from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import queries
from .. import students as st
from ..auth import editor, viewer
from ..db import get_db
from ..service import SaveBusy

router = APIRouter(prefix="/api/v1/students", tags=["students"])


class StudentPatch(BaseModel):
    name: Optional[str] = None
    product: Optional[str] = None
    category: Optional[Literal["Academy", "Intensive", "External"]] = None
    bucket: Optional[str] = None
    tr_cleared: Optional[bool] = None
    mobile: Optional[str] = None
    add_emails: list[str] = []
    remove_emails: list[str] = []
    add_user_ids: list[str] = []
    remove_user_ids: list[str] = []
    unlock: list[str] = []
    note: Optional[str] = None


class MergeIn(BaseModel):
    keep_id: str
    merge_id: str


@router.get("", dependencies=[Depends(viewer)])
def search(q: Optional[str] = None, category: Optional[str] = None, bucket: Optional[str] = None,
           edited: Optional[bool] = None, limit: int = Query(50, ge=1, le=500), skip: int = Query(0, ge=0),
           mobile: Optional[str] = None, email: Optional[str] = None, user_id: Optional[str] = None):
    db = get_db()
    if mobile or email or user_id:   # exact lookup
        out = queries.find_student(db, mobile, email, user_id, None)
        if not out:
            raise HTTPException(404, "Student not found.")
        return out
    return queries.list_students(db, q, category, bucket, edited, limit, skip)


@router.get("/{sid}", dependencies=[Depends(viewer)])
def detail(sid: str):
    db = get_db()
    out = queries.find_student(db, None, None, None, sid)
    if not out:
        raise HTTPException(404, "Student not found.")
    out["edits"] = st.edit_history(db, out["student_id"])
    return out


@router.patch("/{sid}")
def edit(sid: str, body: StudentPatch, user=Depends(editor)):
    db = get_db()
    changes = body.model_dump(exclude_unset=True)
    try:
        result = st.edit_student(db, sid, changes, user)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except st.EditError as exc:
        raise HTTPException(400, str(exc))
    except SaveBusy as exc:
        raise HTTPException(409, str(exc))
    out = detail(sid)
    out["edit_result"] = result
    return out


@router.post("/merge")
def merge(body: MergeIn, user=Depends(editor)):
    try:
        return st.merge_students(get_db(), body.keep_id, body.merge_id, user)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except st.EditError as exc:
        raise HTTPException(400, str(exc))
    except SaveBusy as exc:
        raise HTTPException(409, str(exc))
