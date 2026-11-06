"""Settings read from environment variables (set them in Render → Environment).

For local runs you can instead put them in a file named .env in the backend folder
(see .env.example for the full list).
Real environment variables always win over the .env file.
"""
import os
from pathlib import Path


def _load_dotenv() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key):
            os.environ[key] = value


_load_dotenv()


class Settings:
    def __init__(self) -> None:
        env = os.environ.get
        self.mongodb_uri = env("MONGODB_URI", "").strip()
        self.db_name = env("MONGODB_DB", "applicant_analytics").strip()
        # Optional: lets scripts call the API without logging in (acts as an editor).
        self.api_key = env("API_KEY", "").strip()
        # Login tokens are signed with this. Use a long random value.
        self.jwt_secret = env("JWT_SECRET", "").strip()
        self.token_hours = int(env("TOKEN_HOURS", "12"))
        # First admin account, created on startup when there are no users yet.
        self.admin_email = env("ADMIN_EMAIL", "").strip().lower()
        self.admin_password = env("ADMIN_PASSWORD", "").strip()
        # React app address(es), comma separated, e.g. https://analytics-web.onrender.com
        self.frontend_origins = [o.strip().rstrip("/") for o in env(
            "FRONTEND_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
        # Google service account key (full JSON) used to read the sheets.
        self.google_sa_json = env("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        # Optional: master summary Google Sheet that every saved run is appended to.
        self.master_sheet_url = env("MASTER_SUMMARY_SHEET_URL", "").strip()
        # How long one save may hold the save lock before it is treated as stale.
        self.lock_seconds = int(env("SAVE_LOCK_SECONDS", "600"))


settings = Settings()
