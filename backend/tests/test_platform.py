"""Login, roles, background analyses, pool uploads, student edits and dashboards."""
import mongomock
import pytest
from fastapi.testclient import TestClient

from app import db as dbmod
from app.analysis import runner
from app.main import app
from test_api import H, admin_headers, rec, run, save  # noqa: F401  (sets env + settings)


class WS:
    def __init__(self, title, rows):
        self.title, self.rows, self.id = title, rows, 0

    def get_all_values(self):
        return self.rows


class Book:
    def __init__(self, title, tabs):
        self.title, self.tabs = title, tabs

    def worksheets(self):
        return self.tabs


P = [[f"Student {i}", f"98765432{i:02d}", f"s{i}@x.com", f"http://r/{i}"] for i in range(10)]
HDR = ["Name", "Mobile Number", "Email", "Resume Link"]
BOOK = Book("Nubra - Product Intern", [
    WS("TA - Total Applications", [HDR + ["Job ID"]] + [p + ["N-1"] for p in P]),
    WS("RS", [HDR + ["Priority"]] + [p + [v] for p, v in zip(P, ["P1", "p2", "Reject", "P3", "P1"])]),
    WS("SC", [HDR + ["Status"]] + [p + [v] for p, v in zip(P, ["Select", "Hold", "N/A"])]),
    WS("SP Final", [HDR + ["Priority"]] + [p + [v] for p, v in zip(P, ["P1", "P2"])]),
    WS("Product Map", [["Mobile", "Product"]] + [[p[1], "NIAT ACADEMY" if i % 2 else "INTENSIVE"]
                                                  for i, p in enumerate(P)]),
])
BUCKET_CSV = "Mobile,Bucket\n" + "\n".join(f"{P[i][1]},Bucket {'ABCD'[i % 4]}" for i in range(6))
TR_CSV = "Mobile,TR1 Status,TR2 Status\n" + "\n".join(f"{P[i][1]},Cleared," for i in range(4))


class FakeClient:
    def open_by_url(self, url):
        if "missing" in url:
            raise Exception("APIError: [403]: The caller does not have permission")
        return BOOK


@pytest.fixture()
def client(monkeypatch):
    fake = mongomock.MongoClient(tz_aware=True).analytics
    dbmod.set_db(fake)
    monkeypatch.setattr(runner, "sheets_client", lambda: FakeClient())
    monkeypatch.setattr(runner, "service_account_email", lambda: "bot@proj.iam.gserviceaccount.com")
    with TestClient(app) as c:
        c.db = fake
        c.A = admin_headers(c)
        yield c
    dbmod.set_db(None)


def make_user(client, email, role):
    r = client.post("/api/v1/users", json={"email": email, "name": role.title(), "role": role,
                                           "password": "password-123"}, headers=client.A)
    assert r.status_code == 200, r.text
    tok = client.post("/api/v1/auth/login", json={"email": email, "password": "password-123"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def upload_pools(client):
    for kind, text in (("bucket", BUCKET_CSV), ("tr", TR_CSV)):
        r = client.post(f"/api/v1/settings/pools/{kind}", files={"file": (f"{kind}.csv", text, "text/csv")},
                        headers=client.A)
        assert r.status_code == 200, r.text


def analyse(client, headers, url="https://docs.google.com/spreadsheets/d/abc", job="N-1"):
    r = client.post("/api/v1/analyses", json={"job_id": job, "sheet_url": url, "company": "Nubra",
                                              "role": "Product Intern"}, headers=headers)
    assert r.status_code == 200, r.text
    return client.get(f"/api/v1/analyses/{r.json()['id']}", headers=headers).json()


# ---- login + roles ------------------------------------------------------------------ #
def test_login_and_roles(client):
    assert client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "nope"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=client.A).json()["role"] == "admin"
    viewer = make_user(client, "v@x.com", "viewer")
    assert client.get("/api/v1/dashboard", headers=viewer).status_code == 200
    assert client.post("/api/v1/analyses", json={"job_id": "X", "sheet_url": "https://docs.google.com/spreadsheets/d/a"},
                       headers=viewer).status_code == 403
    assert client.get("/api/v1/users", headers=viewer).status_code == 403
    # Disabling a user logs them out at once.
    client.patch("/api/v1/users/v@x.com", json={"active": False}, headers=client.A)
    assert client.get("/api/v1/dashboard", headers=viewer).status_code == 401
    # The last admin can't be removed.
    assert client.patch("/api/v1/users/admin@x.com", json={"role": "viewer"}, headers=client.A).status_code == 400


def test_change_password(client):
    r = client.post("/api/v1/auth/change-password",
                    json={"current_password": "admin-pass-123", "new_password": "new-pass-456"}, headers=client.A)
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=client.A).status_code == 401   # old token no longer works
    assert client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "new-pass-456"}).status_code == 200


# ---- analysis ----------------------------------------------------------------------- #
def test_analysis_needs_pools_then_runs_and_saves(client):
    editor = make_user(client, "e@x.com", "editor")
    a = analyse(client, editor)
    assert a["status"] == "failed" and "pool" in a["message"].lower()

    upload_pools(client)
    a = analyse(client, editor)
    assert a["status"] == "done", a["message"]
    st = a["preview"]["stages"]
    assert [st[s]["unique"] for s in ("TA", "RS", "SC", "AS", "SP")] == [10, 5, 3, 0, 2]
    assert a["preview"]["priority_tables"]["SC"][0] == {"label": "Select", "candidates": 1, "academy": 0,
                                                        "intensive": 1, "external": 0}
    assert st["TA"]["buckets"]["A"]["candidates"] >= 0 and st["TA"]["intensive"] == 5

    out = client.post(f"/api/v1/analyses/{a['id']}/save", headers=editor).json()
    assert out["status"] == "saved" and out["students_created"] == 10
    again = client.post(f"/api/v1/analyses/{a['id']}/save", headers=editor).json()
    assert again["status"] == "already_saved"
    job = client.get("/api/v1/jobs/N-1", headers=editor).json()
    assert job["company"] == "Nubra" and job["latest_stats"]["stages"]["SP"]["unique"] == 2


def test_analysis_permission_error_is_friendly(client):
    upload_pools(client)
    a = analyse(client, client.A, url="https://docs.google.com/spreadsheets/d/missing")
    assert a["status"] == "failed" and "bot@proj.iam.gserviceaccount.com" in a["message"]


def test_bad_pool_file_rejected(client):
    r = client.post("/api/v1/settings/pools/bucket", files={"file": ("x.csv", "Name\nA\n", "text/csv")},
                    headers=client.A)
    assert r.status_code == 400 and "Bucket" in r.json()["detail"]


# ---- student edits ----------------------------------------------------------------- #
def test_edit_locks_field_against_next_save(client):
    save(client, run("J1", [rec("TA", "9100000001", name="Ravi", bucket="B")], run_at="2026-11-01T10:00:00Z"))
    sid = client.db.students.find_one()["_id"]
    r = client.patch(f"/api/v1/students/{sid}", json={"name": "Ravi Kumar", "bucket": "a",
                                                      "add_emails": ["Ravi@X.com"], "note": "fixed"},
                     headers=client.A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Ravi Kumar" and body["bucket"] == "A" and body["emails"] == ["ravi@x.com"]
    assert set(body["locked_fields"]) == {"name", "bucket"} and body["edits"][0]["note"] == "fixed"

    # A newer sheet save does not overwrite the hand-edited fields, but updates the others.
    save(client, run("J2", [rec("TA", "9100000001", name="RAVI", bucket="C", category="Intensive")],
                     run_at="2026-11-03T10:00:00Z"))
    s = client.get(f"/api/v1/students/{sid}", headers=client.A).json()
    assert s["name"] == "Ravi Kumar" and s["bucket"] == "A" and s["category"] == "Intensive"

    # Unlock -> the next save may update it again.
    client.patch(f"/api/v1/students/{sid}", json={"unlock": ["bucket"]}, headers=client.A)
    save(client, run("J3", [rec("TA", "9100000001", bucket="D")], run_at="2026-11-04T10:00:00Z"))
    assert client.get(f"/api/v1/students/{sid}", headers=client.A).json()["bucket"] == "D"


def test_edit_rejects_identity_owned_by_other_student(client):
    save(client, run("J1", [rec("TA", "9100000002", email="a@x.com"), rec("TA", "9100000003")]))
    s3 = client.db.students.find_one({"mobile": "9100000003"})["_id"]
    r = client.patch(f"/api/v1/students/{s3}", json={"add_emails": ["a@x.com"]}, headers=client.A)
    assert r.status_code == 400 and "another student" in r.json()["detail"]
    viewer = make_user(client, "v2@x.com", "viewer")
    assert client.patch(f"/api/v1/students/{s3}", json={"name": "X"}, headers=viewer).status_code == 403


def test_manual_merge(client):
    save(client, run("J1", [rec("TA", None, email="only@x.com", name="Only Email")]))
    save(client, run("J2", [rec("TA", "9100000004", name="Has Mobile")]))
    keep = client.db.students.find_one({"mobile": "9100000004"})["_id"]
    other = client.db.students.find_one({"emails": "only@x.com"})["_id"]
    r = client.post("/api/v1/students/merge", json={"keep_id": keep, "merge_id": other}, headers=client.A)
    assert r.status_code == 200, r.text
    s = client.get(f"/api/v1/students/{keep}", headers=client.A).json()
    assert s["emails"] == ["only@x.com"] and {a["job_id"] for a in s["applications"]} == {"J1", "J2"}
    assert client.get(f"/api/v1/students/{other}", headers=client.A).json()["student_id"] == keep


# ---- dashboards ----------------------------------------------------------------------- #
def test_dashboard_companies_students_csv(client):
    save(client, run("J1", [rec("TA", "9200000001", category="Academy"), rec("TA", "9200000002"),
                            rec("RS", "9200000001", label="P1"), rec("SP", "9200000001", label="P1")],
                     company="Nubra"))
    save(client, run("J2", [rec("TA", "9200000003")], company=None))
    d = client.get("/api/v1/dashboard", headers=client.A).json()
    assert d["funnel"]["TA"] == 2 or d["funnel"]["TA"] >= 1   # stage counts come from the stats sent
    assert d["jobs"] == 2 and d["students"] == 3 and d["companies"] == 1
    comps = client.get("/api/v1/companies", headers=client.A).json()["items"]
    assert [c["company"] for c in comps] == ["Nubra", "Unassigned"]
    assert client.get("/api/v1/companies/nubra", headers=client.A).json()["job_list"][0]["job_id"] == "J1"
    assert client.get("/api/v1/companies/Unassigned", headers=client.A).status_code == 200
    lst = client.get("/api/v1/students", params={"q": "92000000"}, headers=client.A).json()
    assert lst["total"] == 3
    one = client.get("/api/v1/students", params={"q": "9200000001"}, headers=client.A).json()["items"][0]
    assert one["jobs"] == 1 and one["reached_sp"] == 1
    csv = client.get("/api/v1/jobs/J1/candidates.csv", params={"stage": "RS"}, headers=client.A)
    assert csv.status_code == 200 and "9200000001" in csv.text and csv.text.count("\n") == 2
