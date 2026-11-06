"""Request bodies."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .normalize import STAGES

StageCode = Literal["TA", "RS", "SC", "AS", "SP"]


class BucketStat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidates: int = 0
    tr_cleared: int = 0


class StageStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    present: bool = False
    rows: int = 0
    unique: int = 0
    academy: int = 0
    intensive: int = 0
    external: int = 0
    academy_in_bucket: int = 0
    tr_cleared: int = 0
    academy_tr_cleared: int = 0
    pct_of_ta: float = 0.0
    pct_of_prev: float = 0.0
    buckets: dict[str, BucketStat] = Field(default_factory=dict)
    priority: dict[str, int] = Field(default_factory=dict)


class CandidateRecord(BaseModel):
    """One row of one stage tab, after the app's cleaning and product / bucket matching."""
    model_config = ConfigDict(extra="ignore")
    stage: StageCode
    mobile: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[str] = None
    name: Optional[str] = None
    product: Optional[str] = None
    category: Optional[Literal["Academy", "Intensive", "External"]] = None
    bucket: Optional[str] = None
    tr_cleared: bool = False
    label: Optional[str] = None  # P1 / Reject / Select / ... (TA has none)


class RunIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    job_id: str = Field(min_length=1, max_length=100)
    company: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, max_length=200)
    sheet_url: Optional[str] = Field(default=None, max_length=1000)
    sheet_title: Optional[str] = Field(default=None, max_length=300)
    run_at: Optional[datetime] = None
    tr_rule: Optional[str] = Field(default=None, max_length=200)
    stages: dict[str, StageStats] = Field(default_factory=dict)
    candidates: list[CandidateRecord] = Field(default_factory=list, max_length=300_000)

    @field_validator("job_id")
    @classmethod
    def _job_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("job_id is blank")
        return v.strip()

    @field_validator("stages")
    @classmethod
    def _all_stages(cls, v: dict) -> dict:
        unknown = set(v) - set(STAGES)
        if unknown:
            raise ValueError(f"unknown stage(s): {sorted(unknown)}")
        # A missing stage is stored as all zeros.
        return {s: v.get(s, StageStats()) for s in STAGES}


class JobPatch(BaseModel):
    company: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, max_length=200)
