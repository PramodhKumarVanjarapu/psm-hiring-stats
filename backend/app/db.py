"""MongoDB connection and indexes."""
from pymongo import ASCENDING, DESCENDING, MongoClient

from .config import settings

_client = None
_db_override = None


def get_db():
    """The database used by the API (tests replace it with set_db)."""
    global _client
    if _db_override is not None:
        return _db_override
    if _client is None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not set.")
        _client = MongoClient(settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=10_000)
    return _client[settings.db_name]


def set_db(db) -> None:
    global _db_override
    _db_override = db


def ensure_indexes(db) -> None:
    # students: each mobile / email / user id belongs to at most ONE student.
    db.students.create_index(
        "mobile", unique=True, name="uniq_mobile",
        partialFilterExpression={"mobile": {"$type": "string"}},
    )
    db.students.create_index(
        "emails", unique=True, name="uniq_emails",
        partialFilterExpression={"emails": {"$exists": True}},
    )
    db.students.create_index(
        "user_ids", unique=True, name="uniq_user_ids",
        partialFilterExpression={"user_ids": {"$exists": True}},
    )

    # applications: _id is "<job_key>:<student_id>", so one row per student per job.
    db.applications.create_index("student_id")
    db.applications.create_index([("job_key", ASCENDING), ("furthest_stage", ASCENDING)])
    db.applications.create_index([("job_key", ASCENDING), ("run_id", ASCENDING)])

    # job_stats: _id is the run_id, so the same run can never be stored twice.
    db.job_stats.create_index([("job_key", ASCENDING), ("run_at", DESCENDING)])
    db.job_stats.create_index([("is_latest", ASCENDING), ("company", ASCENDING)])

    db.jobs.create_index([("updated_at", DESCENDING)])
    db.jobs.create_index("company")

    db.identity_conflicts.create_index([("resolved", ASCENDING), ("last_seen", DESCENDING)])
    db.student_merges.create_index("merged_into")

    # Expired save locks are removed automatically.
    db.locks.create_index("expires_at", expireAfterSeconds=0)

    # Unsaved analysis previews are removed after 7 days (saved ones keep no expiry).
    db.analyses.create_index("expires_at", expireAfterSeconds=0)
    db.analyses.create_index([("created_at", DESCENDING)])
    db.student_edits.create_index([("student_id", ASCENDING), ("at", DESCENDING)])
    db.students.create_index("name")
    db.students.create_index([("updated_at", DESCENDING)])
