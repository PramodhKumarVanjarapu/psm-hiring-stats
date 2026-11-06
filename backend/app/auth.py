"""Login (email + password), tokens and role checks.

Roles:  viewer  - read everything
        editor  - + run analyses, save runs, edit students, set company / role, resolve conflicts
        admin   - + manage users, upload pool files, delete jobs
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import timedelta

import jwt
from fastapi import Depends, Header, HTTPException

from .config import settings
from .db import get_db
from .normalize import now_utc

ROLES = ("viewer", "editor", "admin")
_RANK = {r: i for i, r in enumerate(ROLES)}
_ITERATIONS = 240_000


# ---- passwords -------------------------------------------------------------- #
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iters))
        return hmac.compare_digest(test, base64.b64decode(digest))
    except Exception:
        return False


def check_password_rules(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")


def norm_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e):
        raise HTTPException(400, "Enter a valid email address.")
    return e


# ---- tokens -------------------------------------------------------------------- #
def _secret() -> str:
    if not settings.jwt_secret:
        raise HTTPException(500, "JWT_SECRET is not set on the server.")
    return settings.jwt_secret


def make_token(user: dict) -> str:
    now = now_utc()
    payload = {"sub": user["_id"], "role": user["role"], "ver": user.get("token_version", 0),
               "iat": int(now.timestamp()),
               "exp": int((now + timedelta(hours=settings.token_hours)).timestamp())}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def public_user(u: dict) -> dict:
    return {"email": u["_id"], "name": u.get("name"), "role": u["role"], "active": u.get("active", True),
            "created_at": u.get("created_at"), "last_login": u.get("last_login")}


# ---- first admin ------------------------------------------------------------------ #
def ensure_admin(db) -> None:
    if db.users.count_documents({}) > 0 or not (settings.admin_email and settings.admin_password):
        return
    db.users.insert_one({"_id": settings.admin_email, "name": "Admin", "role": "admin", "active": True,
                         "password_hash": hash_password(settings.admin_password),
                         "token_version": 0, "created_at": now_utc()})


# ---- request dependencies ------------------------------------------------------------ #
def current_user(authorization: str = Header(default=""), x_api_key: str = Header(default="")) -> dict:
    if x_api_key:
        if settings.api_key and hmac.compare_digest(x_api_key.encode(), settings.api_key.encode()):
            return {"_id": "api-key", "name": "API key", "role": "editor"}
        raise HTTPException(401, "Wrong X-API-Key.")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Log in first.")
    try:
        data = jwt.decode(authorization[7:].strip(), _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Your session expired. Log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Log in first.")
    user = get_db().users.find_one({"_id": data.get("sub")})
    if not user or not user.get("active", True) or user.get("token_version", 0) != data.get("ver"):
        raise HTTPException(401, "Your account was changed or disabled. Log in again.")
    return user


def require(role: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if _RANK.get(user.get("role"), -1) < _RANK[role]:
            raise HTTPException(403, f"This needs the {role} role.")
        return user
    return dep


viewer = require("viewer")
editor = require("editor")
admin = require("admin")
