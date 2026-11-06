from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import (ROLES, admin, check_password_rules, current_user, hash_password, make_token, norm_email,
                    public_user, verify_password)
from ..db import get_db
from ..normalize import now_utc

router = APIRouter(prefix="/api/v1", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


class UserIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=100)
    role: str = "viewer"
    password: str


class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = None


@router.post("/auth/login")
def login(body: LoginIn):
    db = get_db()
    user = db.users.find_one({"_id": body.email.strip().lower()})
    if not user or not user.get("active", True) or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(401, "Wrong email or password.")
    db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": now_utc()}})
    return {"token": make_token(user), "user": public_user(user)}


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return public_user(user) if user["_id"] != "api-key" else {"email": "api-key", "role": user["role"]}


@router.post("/auth/change-password")
def change_password(body: PasswordIn, user=Depends(current_user)):
    if user["_id"] == "api-key" or not verify_password(body.current_password, user.get("password_hash", "")):
        raise HTTPException(400, "Current password is wrong.")
    check_password_rules(body.new_password)
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password)},
                                                     "$inc": {"token_version": 1}})
    fresh = get_db().users.find_one({"_id": user["_id"]})
    return {"token": make_token(fresh), "user": public_user(fresh)}


# ---- users (admin) ----------------------------------------------------------------- #
@router.get("/users", dependencies=[Depends(admin)])
def users():
    return [public_user(u) for u in get_db().users.find().sort("_id", 1)]


@router.post("/users", dependencies=[Depends(admin)])
def create_user(body: UserIn):
    if body.role not in ROLES:
        raise HTTPException(400, f"Role must be one of {', '.join(ROLES)}.")
    check_password_rules(body.password)
    email = norm_email(body.email)
    db = get_db()
    if db.users.find_one({"_id": email}):
        raise HTTPException(409, "A user with this email already exists.")
    doc = {"_id": email, "name": body.name.strip(), "role": body.role, "active": True, "token_version": 0,
           "password_hash": hash_password(body.password), "created_at": now_utc()}
    db.users.insert_one(doc)
    return public_user(doc)


@router.patch("/users/{email}")
def update_user(email: str, body: UserPatch, me_user=Depends(admin)):
    db = get_db()
    email = email.strip().lower()
    u = db.users.find_one({"_id": email})
    if not u:
        raise HTTPException(404, "User not found.")
    sets, bump = {}, False
    if body.name is not None and body.name.strip():
        sets["name"] = body.name.strip()
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(400, f"Role must be one of {', '.join(ROLES)}.")
        sets["role"], bump = body.role, bump or body.role != u["role"]
    if body.active is not None:
        sets["active"], bump = body.active, bump or body.active != u.get("active", True)
    if body.password:
        check_password_rules(body.password)
        sets["password_hash"], bump = hash_password(body.password), True
    losing_admin = u["role"] == "admin" and (sets.get("role", "admin") != "admin" or sets.get("active") is False)
    if losing_admin and db.users.count_documents({"role": "admin", "active": {"$ne": False}}) <= 1:
        raise HTTPException(400, "There must be at least one active admin.")
    update = {"$set": sets} if sets else {}
    if bump:
        update["$inc"] = {"token_version": 1}   # logs the user out everywhere
    if update:
        db.users.update_one({"_id": email}, update)
    return public_user(db.users.find_one({"_id": email}))
