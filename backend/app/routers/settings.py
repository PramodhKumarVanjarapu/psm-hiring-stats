from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..analysis import pools
from ..analysis.sheets import service_account_email
from ..auth import admin, viewer
from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
MAX_UPLOAD = 80 * 1024 * 1024


@router.get("", dependencies=[Depends(viewer)])
def info():
    return {"pools": pools.pool_info(get_db()), "service_account_email": service_account_email(),
            "master_sheet_configured": bool(settings.master_sheet_url)}


@router.post("/pools/{kind}")
async def upload_pool(kind: str, file: UploadFile = File(...), user=Depends(admin)):
    if kind not in pools.POOL_FILES:
        raise HTTPException(404, "Unknown pool. Use 'bucket' or 'tr'.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, "The file is larger than 80 MB.")
    try:
        return pools.save_pool(get_db(), kind, file.filename or pools.POOL_FILES[kind], data, user["_id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
