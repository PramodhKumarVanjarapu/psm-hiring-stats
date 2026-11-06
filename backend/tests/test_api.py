"""Run with:  pytest -q   (uses an in-memory fake MongoDB, no real database needed)"""
import os
import uuid

os.environ["API_KEY"] = "test-key"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_EMAIL"] = "admin@x.com"
os.environ["ADMIN_PASSWORD"] = "admin-pass-123"

import mongomock
import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.config import settings
from app.main import app

settings.api_key = "test-key"
settings.jwt_secret = "test-secret"
settings.admin_email, settings.admin_password = "admin@x.com", "admin-pass-123"
H = {"X-API-Key": "test-key"}


def admin_headers(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "admin-pass-123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def client():
    fake = mongomock.MongoClient(tz_aware=True).analytics
    dbmod.set_db(fake)
    with TestClient(app) as c:
        c.db = fake
        yield c
    dbmod.set_db(None)


def rec(stage, mobile=None, email=None, uid=None, label=None, **kw):
    return {"stage": stage, "mobile": mobile, "email": email, "user_id": uid, "label": label,
            "name": kw.get("name"), "product": kw.get("product"), "category": kw.get("category", "Academy"),
            "bucket": kw.get("bucket"), "tr_cleared": kw.get("tr", False)}


def run(job="J1", candidates=(), run_at="2026-11-06T10:00:00+05:30", run_id=None, **kw):
    return {"run_id": run_id or uuid.uuid4().hex, "job_id": job, "run_at": run_at,
            "sheet_url": kw.get("sheet_url", "https://docs.google.com/spreadsheets/d/a"),
            "company": kw.get("company"), "stages": {"TA": {"present": True, "unique": len(candidates)}},
            "candidates": list(candidates)}


def save(client, body, code=200):
    r = client.post("/api/v1/runs", json=body, headers=H)
    assert r.status_code == code, r.text
    return r.json()


def test_auth_required(client):
    assert client.post("/api/v1/runs", json=run()).status_code == 401
    assert client.get("/api/v1/jobs", headers={"X-API-Key": "wrong"}).status_code == 401


def test_same_person_many_rows_in_one_run(client):
    body = run(candidates=[
        rec("TA", "+91 98765 43210", name="Asha"),
        rec("TA", "9876543210"),                      # repeat application
        rec("RS", "919876543210", label="P2"),
        rec("RS", "9876543210", label="P1"),          # listed twice: best label wins
        rec("SP", None, email="ASHA@x.com", label="P3"),  # only email here...
        rec("SC", "9876543210", email="asha@x.com", label="Select"),  # ...linked by this row
    ])
    out = save(client, body)
    assert out["people_in_run"] == 1 and out["students_created"] == 1 and out["applications"] == 1
    app_doc = client.db.applications.find_one()
    assert app_doc["stages"] == {"TA": "Applied", "RS": "P1", "SC": "Select", "AS": None, "SP": "P3"}
    assert app_doc["furthest_stage"] == "SP"


def test_same_student_across_jobs_is_not_duplicated(client):
    save(client, run("J1", [rec("TA", "9000000001", name="Ravi")]))
    save(client, run("J2", [rec("TA", "9000000001", email="ravi@x.com")]))
    assert client.db.students.count_documents({}) == 1
    s = client.get("/api/v1/students", params={"email": "Ravi@X.com"}, headers=H).json()
    assert {a["job_id"] for a in s["applications"]} == {"J1", "J2"}
    assert s["name"] == "Ravi"


def test_email_only_student_merged_when_mobile_appears(client):
    save(client, run("J1", [rec("TA", None, email="kiran@x.com")]), )
    save(client, run("J2", [rec("TA", "9000000002", uid="U77")]))
    assert client.db.students.count_documents({}) == 2
    # This row links both students: they are the same person.
    out = save(client, run("J3", [rec("TA", "9000000002", email="kiran@x.com")]))
    assert out["students_merged"] == 1
    assert client.db.students.count_documents({}) == 1
    s = client.db.students.find_one()
    assert s["mobile"] == "9000000002" and s["emails"] == ["kiran@x.com"] and s["user_ids"] == ["u77"]
    assert client.db.applications.count_documents({"student_id": s["_id"]}) == 3
    assert client.db.student_merges.count_documents({}) == 1
    old_id = client.db.student_merges.find_one()["_id"]
    found = client.get(f"/api/v1/students/{old_id}", headers=H).json()
    assert found["student_id"] == s["_id"]


def test_different_mobiles_sharing_email_are_not_merged(client):
    out = save(client, run("J1", [rec("TA", "9000000003", email="shared@x.com"),
                                  rec("TA", "9000000004", email="shared@x.com")]))
    assert out["students_created"] == 2 and out["identity_conflicts"] == 1
    # The same clash again (new job) is counted, not stored twice.
    save(client, run("J2", [rec("TA", "9000000004", email="shared@x.com")]))
    conflicts = client.get("/api/v1/identity-conflicts", headers=H).json()
    assert conflicts["total"] == 1 and conflicts["items"][0]["seen_count"] == 2
    assert client.db.students.count_documents({"emails": "shared@x.com"}) == 1
    cid = conflicts["items"][0]["id"]
    assert client.post(f"/api/v1/identity-conflicts/{cid}/resolve", headers=H).status_code == 200


def test_same_run_sent_twice_is_saved_once(client):
    body = run(candidates=[rec("TA", "9000000005")])
    assert save(client, body)["status"] == "saved"
    again = save(client, body)
    assert again["status"] == "already_saved"
    assert client.db.job_stats.count_documents({}) == 1
    body2 = {**body, "job_id": "OTHER"}
    save(client, body2, code=409)


def test_rerun_replaces_applications_and_keeps_history(client):
    save(client, run("J1", [rec("TA", "9000000006"), rec("TA", "9000000007")], run_at="2026-11-01T10:00:00Z"))
    out = save(client, run(" j1 ", [rec("TA", "9000000006"), rec("RS", "9000000006", label="P1")],
                           run_at="2026-11-02T10:00:00Z"))
    assert out["applications_removed"] == 1                     # 9000000007 is no longer in the sheet
    assert client.db.applications.count_documents({"job_key": "J1"}) == 1
    assert client.db.job_stats.count_documents({"job_key": "J1", "is_latest": True}) == 1
    assert len(client.get("/api/v1/jobs/J1/runs", headers=H).json()) == 2
    assert client.db.jobs.count_documents({}) == 1               # ' j1 ' and 'J1' are one job


def test_older_run_saved_late_does_not_replace_latest(client):
    save(client, run("J1", [rec("TA", "9000000008", bucket="Bucket A")], run_at="2026-11-05T10:00:00Z"))
    out = save(client, run("J1", [rec("TA", "9000000009")], run_at="2026-11-01T10:00:00Z"))
    assert out["is_latest"] is False and out["warnings"]
    assert client.db.applications.count_documents({"job_key": "J1"}) == 1
    latest = client.get("/api/v1/jobs/J1", headers=H).json()["latest_stats"]
    assert latest["run_at"].startswith("2026-11-05")


def test_save_lock_blocks_parallel_save(client):
    from datetime import datetime, timedelta, timezone
    client.db.locks.insert_one({"_id": "save", "token": "x",
                                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)})
    save(client, run(candidates=[rec("TA", "9000000010")]), code=409)
    # A stale lock (crashed save) is taken over.
    client.db.locks.update_one({"_id": "save"}, {"$set": {"expires_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}})
    save(client, run(candidates=[rec("TA", "9000000010")]))


def test_queries(client):
    save(client, run("J1", [
        rec("TA", "9000000011", bucket="a", category="Academy"),
        rec("RS", "9000000011", label="P1"),
        rec("SP", "9000000011", label="P2"),
        rec("TA", "9000000012", category="Intensive"),
        rec("RS", "9000000012", label="Reject"),
    ], company="Nubra"))
    c = client.get("/api/v1/jobs/J1/candidates", params={"stage": "RS", "label": "P1"}, headers=H).json()
    assert c["total"] == 1 and c["items"][0]["mobile"] == "9000000011"
    assert client.get("/api/v1/jobs/J1/candidates", params={"furthest_stage": "SP"}, headers=H).json()["total"] == 1
    assert client.get("/api/v1/jobs", params={"company": "nubra"}, headers=H).json()["total"] == 1
    assert client.patch("/api/v1/jobs/J1", json={"role": "Product Intern"}, headers=H).json()["role"] == "Product Intern"
    assert client.get("/api/v1/reports/funnel", headers=H).status_code == 200
    assert client.get("/api/v1/reports/buckets", headers=H).status_code == 200
    assert client.delete("/api/v1/jobs/J1", headers=H).status_code == 403          # API key = editor
    A = admin_headers(client)
    assert client.delete("/api/v1/jobs/J1", headers=A).status_code == 400
    assert client.delete("/api/v1/jobs/J1", params={"confirm": "true"}, headers=A).json()["applications_deleted"] == 2
    assert client.db.students.count_documents({}) == 2  # students are kept


def test_rows_without_any_id_are_skipped(client):
    out = save(client, run(candidates=[rec("TA", "123"), rec("TA", None, email="not-an-email")]))
    assert out["rows_skipped"] == 2 and out["students_created"] == 0
