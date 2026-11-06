"""Google Sheets access through the service account."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ..config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
KEY_FILES = [Path(__file__).resolve().parents[2] / "service_account.json",
             Path("/etc/secrets/service_account.json")]


def _key_info() -> dict:
    if settings.google_sa_json:
        return json.loads(settings.google_sa_json)
    for path in KEY_FILES:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise RuntimeError("No Google service account key. Set GOOGLE_SERVICE_ACCOUNT_JSON or put "
                       "service_account.json in the backend folder.")


def service_account_email() -> str:
    try:
        return _key_info().get("client_email", "")
    except Exception:
        return ""


@lru_cache(maxsize=1)
def sheets_client():
    import gspread
    from google.oauth2.service_account import Credentials
    return gspread.authorize(Credentials.from_service_account_info(_key_info(), scopes=SCOPES))


def worksheet_for_url(client, url: str):
    book = client.open_by_url(url.strip())
    m = re.search(r"[?#&]gid=(\d+)", url)
    if m:
        for ws in book.worksheets():
            if ws.id == int(m.group(1)):
                return ws
    return book.sheet1
