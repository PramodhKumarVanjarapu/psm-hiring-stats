"""One internal Google Sheet in -> all stage stats out (moved here from the Streamlit app).

Tabs are read by name: TA (required), RS (required), SC, AS, SP (required). Every tab that has a
Product column plus a mobile / email / user id column is used for product mapping.
All stats are on UNIQUE candidates.
"""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from . import core

ACADEMY_KW = ["ACADEMY"]
INTENSIVE_KW = ["INTENSIVE"]
TR_RULE = core.TR_RULES[0]
CLEARED_VALUES = ["cleared"]
BUCKETS = list(core.BUCKET_LETTERS)

STAGES = {
    "TA": "Total Applications",
    "RS": "Resume Shortlisted",
    "SC": "Screening Shortlisted",
    "AS": "Assignment Shortlisted",
    "SP": "Final Profiles Shared",
}
REQUIRED_STAGES = ("TA", "RS", "SP")
_STAGE_RE = re.compile(r"^\s*(" + "|".join(STAGES) + r")(?![A-Za-z])", re.IGNORECASE)

STAGE_LABELS = {
    "RS": ["P1", "P2", "P3", "Reject"],
    "SC": ["Select", "Reject", "Hold", "NA"],
    "AS": ["P1", "P2", "P3"],
    "SP": ["P1", "P2", "P3"],
}
OTHER_LABEL = "Other / blank"
_LABEL_ALIASES = {"SELECT": "Select", "SELECTED": "Select", "REJECT": "Reject", "REJECTED": "Reject",
                  "HOLD": "Hold", "ONHOLD": "Hold", "NA": "NA", "NOTAPPLICABLE": "NA"}
STATUS_KW = ["status", "screeningstatus", "result", "decision", "outcome"]

STD = {"name": "Name", "mobile": "Mobile", "email": "Email", "uid": "User ID",
       "product": "Product", "resume": "Resume", "priority": "Priority"}
_BUCKET_KEYS = {"Other bucket (not A-D)": "other", "Not in bucket": "not_in_bucket"}


class SheetError(ValueError):
    """A problem with the sheet the user can fix (wrong link, missing tabs, ...)."""


# --------------------------------------------------------------------------- #
# Reading tabs
# --------------------------------------------------------------------------- #
def worksheet_to_df(values: list[list]) -> pd.DataFrame:
    if not values:
        return pd.DataFrame()
    # The header row is not always row 1: use the first of the top 10 rows that looks like one.
    hdr = 0
    for i, r in enumerate(values[:10]):
        if any(k in core.norm_col(c) for c in r for k in ("mobile", "phone", "email", "userid", "resume", "product")):
            hdr = i
            break
    headers = [str(x).strip() or f"Unnamed: {i + 1}" for i, x in enumerate(values[hdr])]
    width = len(headers)
    rows = [(list(r) + [""] * width)[:width] for r in values[hdr + 1:]]
    df = pd.DataFrame(rows, columns=headers)
    if df.empty:
        return df
    blank = df.apply(lambda row: all(not str(v).strip() for v in row), axis=1)
    return df.loc[~blank].reset_index(drop=True)


def stage_of(title: str):
    m = _STAGE_RE.match(str(title))
    return m.group(1).upper() if m else None


def is_product_tab(title: str) -> bool:
    return "product" in core.norm_col(title)


# Name columns: headers like "Name", "Student Name", "Candidate", "Applicant Full Name",
# or a "First Name" + "Last Name" pair. Columns that name something else are skipped.
_NAME_EXACT = ["name", "studentname", "candidatename", "applicantname", "fullname", "studentfullname",
               "candidatefullname", "nameofthestudent", "nameofthecandidate", "studentsname", "candidatesname",
               "candidate", "student", "applicant", "studentdetails", "candidatedetails"]
_NAME_NOT = ("company", "college", "mail", "product", "job", "role", "father", "mother", "parent", "guardian",
             "file", "sheet", "user", "drive", "institute", "university", "school", "course", "branch", "city",
             "state", "project", "manager", "recruiter", "poc", "reference", "referrer", "tab", "id", "number",
             "mobile", "phone", "status", "priority", "resume", "link", "url", "batch", "cohort", "bucket",
             "last", "surname", "middle", "nick", "display", "github", "linkedin")


def _looks_like_names(col: pd.Series) -> bool:
    vals = [str(v).strip() for v in col if not core._is_junk(v)][:200]
    if not vals:
        return False
    ok = sum(bool(re.fullmatch(r"[^\W\d_][^\d@]{1,80}", v)) for v in vals)   # letters (any script), no digits / @
    return ok / len(vals) >= 0.7


def find_name(df: pd.DataFrame):
    """Return (Series of names or None, description of the column(s) used)."""
    cols = {c: core.norm_col(c) for c in df.columns}
    first = next((c for c, n in cols.items() if n in ("firstname", "givenname", "studentfirstname", "candidatefirstname")), None)
    last = next((c for c, n in cols.items() if n in ("lastname", "surname", "familyname", "studentlastname", "candidatelastname")), None)
    for kw in _NAME_EXACT:                      # exact header match first
        for c, n in cols.items():
            # Headers that say "name" are trusted; "Candidate" / "Student" must hold name-like values.
            if n == kw and ("name" in kw or _looks_like_names(df[c])):
                return df[c], c
    if first:                                    # "First Name" (+ "Last Name")
        if last:
            full = (df[first].astype(str).str.strip() + " " + df[last].astype(str).str.strip()).str.strip()
            return full.where(full != "", None), f"{first} + {last}"
        return df[first], first
    for c, n in cols.items():                    # any other header that mentions a name
        if "name" in n and not any(x in n for x in _NAME_NOT) and _looks_like_names(df[c]):
            return df[c], c
    return None, ""


def standardise(df: pd.DataFrame, tab: str) -> pd.DataFrame:
    det = core.detect_columns(df)
    out = pd.DataFrame(index=df.index)
    for key, std in STD.items():
        out[std] = df[det[key]] if det.get(key) else ""
    names, name_col = find_name(df)
    out["Name"] = names if names is not None else ""
    out["_Name Col"] = name_col
    # A 10-digit mobile number stored in a "UID" column is treated as the mobile.
    if not det.get("mobile") and det.get("uid") and len(df):
        uid_vals = df[det["uid"]]
        if uid_vals.map(lambda v: core.norm_mobile(v) is not None).mean() >= 0.8:
            out["Mobile"] = uid_vals
            out["User ID"] = ""
    pcol = det.get("priority") or core.find_col(df, STATUS_KW, exclude=("tr1", "tr2", "trstatus"))
    if pcol:
        out["Priority"] = df[pcol]
    out["_Priority Col"] = pcol or ""
    job_col = core.find_col(df, ["jobid", "jdid", "jobcode", "requisitionid"])
    out["Job ID"] = df[job_col] if job_col else ""
    out["_Source Tab"] = tab
    return out


def load_workbook(book, progress=lambda msg: None) -> dict:
    """`book` is a gspread Spreadsheet (or anything with .title and .worksheets())."""
    frames = {c: [] for c in STAGES}
    used = {c: [] for c in STAGES}
    product_sources, skipped = [], []
    name_sources = []    # (tab title, standardised frame, name column) of every tab that has names

    worksheets = book.worksheets()
    for n, ws in enumerate(worksheets, 1):
        progress(f"Reading tab {n} of {len(worksheets)}: {ws.title}")
        df = worksheet_to_df(ws.get_all_values())
        if df.empty:
            skipped.append(f"{ws.title} (empty)")
            continue
        det = core.detect_columns(df)
        code = stage_of(ws.title)
        has_identity = bool(det.get("mobile") or det.get("uid") or det.get("email"))
        if has_identity:
            std_all = standardise(df, ws.title)
            if std_all["_Name Col"].iloc[0]:
                # Stage tabs first (TA before the rest), then other tabs in sheet order.
                rank = list(STAGES).index(code) if code else len(STAGES)
                name_sources.append((rank, n, ws.title, std_all, std_all["_Name Col"].iloc[0]))
        if det.get("product") and has_identity:
            entry = (ws.title, standardise(df, ws.title), det["product"])
            if is_product_tab(ws.title):
                product_sources.insert(sum(is_product_tab(t) for t, _, _ in product_sources), entry)
            else:
                product_sources.append(entry)

        if code:
            std = standardise(df, ws.title)
            identity = std["Mobile"].map(core.norm_mobile).notna() | std["Email"].map(core.norm_email).notna() \
                | std["User ID"].map(core.norm_text).notna()
            if code == "TA" and det.get("resume"):
                identity &= ~std["Resume"].map(core._is_junk)
            std = std[identity]
            if std.empty:
                skipped.append(f"{ws.title} ({code} tab, but no rows with mobile / email / user id; "
                               f"columns seen: {list(df.columns)[:15]})")
                continue
            frames[code].append(std)
            used[code].append(f"{ws.title} ({len(std):,} rows)")
        elif det.get("product") and has_identity:
            pass
        elif is_product_tab(ws.title):
            skipped.append(f"{ws.title} (looks like a product tab, but needs a 'Product' column and a "
                           f"mobile / email / user id column; columns seen: {list(df.columns)[:15]})")
        else:
            skipped.append(f"{ws.title} (name does not start with {', '.join(STAGES)})")

    missing = [c for c in REQUIRED_STAGES if not frames[c]]
    if missing:
        raise SheetError("Required tab(s) not found or have no candidate rows: "
                         + ", ".join(f"{c} ({STAGES[c]})" for c in missing)
                         + ". SC and AS are optional and count as 0 when missing.")
    return {"stages": {c: pd.concat(f, ignore_index=True) if f else pd.DataFrame() for c, f in frames.items()},
            "used": used, "product_sources": product_sources, "skipped": skipped, "sheet_title": book.title,
            "name_sources": [(t, f, c) for _, _, t, f, c in sorted(name_sources, key=lambda x: (x[0], x[1]))]}


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
def build_product_lookup_all(sources) -> tuple[dict, list]:
    lookup, used = {}, []
    for title, df, product_col in sources:
        part = core.build_product_lookup(df, ACADEMY_KW, INTENSIVE_KW, source=f"{title} tab")
        for key, val in part.items():
            cur = lookup.get(key)
            if cur is None or core._CAT_RANK[val[1]] < core._CAT_RANK[cur[1]]:
                lookup[key] = val
        filled = int((~df["Product"].map(core._is_junk)).sum())
        used.append(f"{title} (column '{product_col}', {filled:,} rows with a product)")
    return lookup, used


def stage_label(value, code: str) -> str:
    v = str(value).strip()
    if v == core.NO_PRIORITY:
        return "NA" if "NA" in STAGE_LABELS[code] else OTHER_LABEL
    label = v if re.fullmatch(r"P\d+", v) else _LABEL_ALIASES.get(core.norm_col(v).upper(), v)
    return label if label in STAGE_LABELS[code] else OTHER_LABEL


def priority_table(cand: pd.DataFrame, code: str) -> list[dict]:
    labels = STAGE_LABELS[code] + [OTHER_LABEL]
    if cand.empty:
        return [{"label": l, "candidates": 0, "academy": 0, "intensive": 0, "external": 0} for l in labels]
    lab = cand["Priority"].map(lambda v: stage_label(v, code))
    cat = cand["Category"].fillna("External")
    out = []
    for l in labels:
        m = lab.eq(l)
        out.append({"label": l, "candidates": int(m.sum()), "academy": int((m & cat.eq("Academy")).sum()),
                    "intensive": int((m & cat.eq("Intensive")).sum()),
                    "external": int((m & cat.eq("External")).sum())})
    return out


def _process(std_df, product_lookup, pools, tr_sum):
    if std_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    cols = {k: STD[k] for k in STD}
    prepared = core.prepare_company(std_df, cols, None, {}, None, None, ACADEMY_KW, INTENSIVE_KW)
    prepared = core.apply_products(prepared, product_lookup, ACADEMY_KW, INTENSIVE_KW)
    matched = core.match_company(prepared, pools, tr_sum)
    return matched, core.unique_candidates(matched)


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or core._is_junk(v):
        return None
    return str(v).strip()


def build_name_lookup(sources) -> tuple[dict, list]:
    """identity key (mobile / user id / email) -> name, from every tab that has a name column.
    The first tab that names a person wins (TA, then RS ... SP, then other tabs)."""
    lookup, used = {}, []
    for title, df, col in sources:
        filled = 0
        for mob, uid, email, name in zip(df["Mobile"], df["User ID"], df["Email"], df["Name"]):
            name = _clean(name)
            if not name:
                continue
            filled += 1
            for key in (f"mob:{core.norm_mobile(mob)}" if core.norm_mobile(mob) else None,
                        f"uid:{core.norm_text(uid)}" if core.norm_text(uid) else None,
                        f"email:{core.norm_email(email)}" if core.norm_email(email) else None):
                if key and key not in lookup:
                    lookup[key] = name
        used.append(f"{title} (column '{col}', {filled:,} rows with a name)")
    return lookup, used


def _name_for(r, names: dict):
    own = _clean(r.get("Name"))
    if own:
        return own
    for prefix, col in (("mob", "_mob"), ("uid", "_uid"), ("email", "_email")):
        v = r.get(col)
        if isinstance(v, str) and f"{prefix}:{v}" in names:
            return names[f"{prefix}:{v}"]
    return None


def _records(matched: dict, names: dict | None = None) -> list[dict]:
    names = names or {}
    records = []
    for code in STAGES:
        m = matched[code]
        if m.empty:
            continue
        for _, r in m.iterrows():
            cat = r.get("Category")
            records.append({
                "stage": code,
                "mobile": _clean(r.get("_mob")) or _clean(core.norm_mobile(r.get("Mobile"))),
                "email": _clean(r.get("_email")), "user_id": _clean(r.get("_uid")),
                "name": _name_for(r, names), "product": _clean(r.get("Product")),
                "category": cat if cat in ("Academy", "Intensive", "External") else None,
                "bucket": _clean(r.get("Bucket")), "tr_cleared": bool(r.get("TR Cleared", False)),
                "label": None if code == "TA" else stage_label(r.get("Priority", core.NO_PRIORITY), code),
            })
    return records


def analyse(book, pools: dict, job_id: str, progress=lambda msg: None) -> dict:
    """Read the workbook and compute everything. Returns {"preview": ..., "stages": ..., "candidates": ...}."""
    wb = load_workbook(book, progress)
    progress("Matching products, buckets and TR status")
    tr_sum = core.tr_summary(pools, TR_RULE, CLEARED_VALUES)
    lookup, product_tabs = build_product_lookup_all(wb["product_sources"])
    names, name_tabs = build_name_lookup(wb["name_sources"])
    matched, unique = {}, {}
    for code in STAGES:
        matched[code], unique[code] = _process(wb["stages"][code], lookup, pools, tr_sum)

    progress("Calculating stats")
    stages, prev, ta = {}, None, len(unique["TA"])
    for code, name in STAGES.items():
        u = unique[code]
        s = core.candidate_stats(u, code)
        n = s["Unique candidates"]
        stages[code] = {
            "present": bool(wb["used"][code]),
            "rows": int(len(matched[code])),
            "unique": int(n),
            "academy": int(s["Academy"]), "intensive": int(s["Intensive"]), "external": int(s["External"]),
            "academy_in_bucket": int(s["Academy in bucket (A-D)"]),
            "tr_cleared": int(s["TR cleared"]), "academy_tr_cleared": int(s["Academy TR cleared"]),
            "pct_of_ta": round(100 * n / ta, 1) if ta else 0.0,
            "pct_of_prev": round(100 * n / prev, 1) if prev else (100.0 if code == "TA" else 0.0),
            "buckets": {_BUCKET_KEYS.get(r["Bucket"], r["Bucket"]):
                        {"candidates": int(r["Candidates"]), "tr_cleared": int(r["TR cleared"])}
                        for _, r in core.bucket_table(u).iterrows()},
            "priority": ({row["label"]: row["candidates"] for row in priority_table(u, code)}
                         if code in STAGE_LABELS else {}),
        }
        prev = n

    sheet_jobs = sorted({str(x).strip() for x in wb["stages"]["TA"]["Job ID"] if str(x).strip()})
    warnings = []
    missing = [c for c in STAGES if not wb["used"][c]]
    if missing:
        warnings.append(f"No tab found for {', '.join(missing)}, so every {'/'.join(missing)} number is 0.")
    if sheet_jobs and job_id.strip() not in sheet_jobs:
        warnings.append(f"The TA tab lists Job ID(s) {', '.join(sheet_jobs[:5])}, which don't match "
                        f"the Job ID you entered.")
    if not product_tabs:
        warnings.append("No tab has a 'Product' column next to a mobile / email / user id column, "
                        "so every candidate is counted as External.")

    priority_cols = {c: sorted({x for x in wb["stages"][c].get("_Priority Col", pd.Series(dtype=str)) if x})
                     for c in STAGES}
    name_cols = {c: sorted({x for x in wb["stages"][c].get("_Name Col", pd.Series(dtype=str)) if x})
                 for c in STAGES}
    if not name_tabs:
        warnings.append("No tab has a name column next to a mobile / email / user id column, so student names "
                        "will be blank. Name the column 'Name', 'Student Name' or 'Candidate Name'.")
    preview = {
        "sheet_title": wb["sheet_title"],
        "stages": stages,
        "priority_tables": {c: priority_table(unique[c], c) for c in STAGE_LABELS},
        "product_tables": {c: [{"category": r["Product category"], "candidates": int(r["Candidates"]),
                                "tr_cleared": int(r["TR cleared"]), "tr_cleared_pct": float(r["TR cleared %"])}
                               for _, r in core.product_table(unique[c]).iterrows()] for c in STAGES},
        "checks": {
            "tabs_used": wb["used"], "product_tabs": product_tabs, "skipped": wb["skipped"],
            "priority_columns": priority_cols,
            "name_columns": name_cols,
            "name_tabs": name_tabs,
            "row_counts": {c: {"rows": int(len(matched[c])), "unique": int(len(unique[c]))} for c in STAGES},
        },
        "warnings": warnings,
    }
    return {"preview": preview, "stages": stages, "candidates": _records(matched, names),
            "summary_row": summary_row(stages, job_id)}


def summary_row(stages: dict, job_id: str, sheet_url: str = "") -> dict:
    """Flat row for the optional master Google Sheet (same columns as the Streamlit app)."""
    row = {"Run timestamp (IST)": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"),
           "Job ID": job_id, "Sheet URL": sheet_url, "TR cleared rule": TR_RULE}
    names = {"unique": "Unique candidates", "academy": "Academy", "intensive": "Intensive",
             "external": "External", "academy_in_bucket": "Academy in bucket (A-D)",
             "tr_cleared": "TR cleared", "academy_tr_cleared": "Academy TR cleared"}
    for code in STAGES:
        s = stages[code]
        row[f"{code} rows"] = s["rows"]
        for k, label in names.items():
            row[f"{code} {label}"] = s[k]
        for label, n in s["priority"].items():
            row[f"{code} {label}"] = n
        for b in BUCKETS:
            row[f"{code} Academy Bucket {b}"] = s["buckets"].get(b, {}).get("candidates", 0)
            row[f"{code} Academy Bucket {b} TR cleared"] = s["buckets"].get(b, {}).get("tr_cleared", 0)
    return row


def append_summary(client, master_url: str, row: dict) -> None:
    from .sheets import worksheet_for_url
    ws = worksheet_for_url(client, master_url)
    existing = ws.get_all_values()
    headers = list(row.keys())
    if not existing:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    else:
        existing_headers = [str(x).strip() for x in existing[0]]
        missing = [h for h in headers if h not in existing_headers]
        if missing:
            existing_headers.extend(missing)
            ws.update(range_name="1:1", values=[existing_headers])
        headers = existing_headers
    ws.append_row([row.get(h, "") for h in headers], value_input_option="USER_ENTERED")