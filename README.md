# Hiring funnel

React app + FastAPI backend + MongoDB for placement hiring stats (TA → RS → SC → AS → SP).

```
frontend/   React app (what people use in the browser)
backend/    FastAPI API: reads the Google Sheets, calculates stats, stores everything in MongoDB
render.yaml Deploys both on Render
```

## What you need

- MongoDB Atlas (free cluster) connection string
- The Google service account key (the same `service_account.json` as before)
- The two lookup CSVs: `offline_attended_pool.csv` and `assessment_pool_main.csv`
  (you upload these from the Settings page after the first login)
- Python 3.12 and Node.js 20 or newer for running on your laptop

## Run on your laptop

### 1. Backend (terminal 1)

```bash
cd backend
python -m venv venv
source venv/Scripts/activate        # Mac / Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # then open .env and fill it in
uvicorn app.main:app --reload --env-file .env
```

In `.env`, fill in at least:

| Name | What to put |
|---|---|
| `MONGODB_URI` | Your Atlas connection string |
| `MONGODB_DB` | `applicant_analytics_local` (keeps test data separate) |
| `JWT_SECRET` | Any long random text. Make one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Your login. The account is created the first time the backend starts |
| `FRONTEND_ORIGINS` | `http://localhost:5173` |

For Google access, put `service_account.json` in the `backend` folder (easiest locally),
or paste the whole key into `GOOGLE_SERVICE_ACCOUNT_JSON` on one line.

Check: http://localhost:8000/health should show `"database": "ok"`.

### 2. React app (terminal 2)

```bash
cd frontend
npm install
cp .env.example .env                # VITE_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:5173 and log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### 3. First steps in the app

1. **Settings → Lookup files:** upload the bucket and TR pool CSVs.
2. **Settings → Users:** add your team (viewer, editor or admin).
3. **New analysis:** enter Job ID, sheet link and company, wait for the preview, then **Save to database**.

## Deploy on Render

1. Put this whole folder in a GitHub repo. `.env`, `service_account.json` and `node_modules` are in `.gitignore`. Don't commit them.
2. In Render: **New → Blueprint**, pick the repo. It creates `hiring-funnel-api` and `hiring-funnel-web`.
3. Fill in the values it asks for:
   - API: `MONGODB_URI`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `GOOGLE_SERVICE_ACCOUNT_JSON` (whole key on one line), `FRONTEND_ORIGINS` (the web app's address).
   - Web: `VITE_API_URL` (the API's address).
   You only know the two addresses after the first deploy. Fill them in, then redeploy both.
   `JWT_SECRET` is generated for you.
4. In MongoDB Atlas → Network Access, allow `0.0.0.0/0` (Render's free plan has no fixed IP).
5. Open the web app, log in, and upload the two lookup CSVs on the Settings page.

Notes:
- The free API sleeps when unused; the first request after a while can take about a minute.
- After changing `VITE_API_URL`, redeploy the web app (it's built into the app at build time).

## Roles

| Role | Can |
|---|---|
| Viewer | See everything |
| Editor | + run and save analyses, edit and merge students, set company / role, mark conflicts as checked |
| Admin | + manage users, upload lookup files, delete jobs |

## How data is kept clean

- One student record per person, matched by mobile, email or user id.
- Two different mobile numbers are never merged automatically. The clash shows on **Identity conflicts**.
- Saving the same analysis twice stores it once. Saving a job again keeps the old run in its history.
- Fields edited by hand are marked "edited", and sheet saves don't overwrite them until you unlock them.
- Stage values (P1, Select, …) always come from the sheet. To change them, fix the sheet and run the job again.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```
