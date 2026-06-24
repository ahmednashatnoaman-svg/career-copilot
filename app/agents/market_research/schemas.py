from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

MarketMode = Literal["egypt", "freelance", "international"]
LaneType = Literal[
    "postings",
    "trends",
    "salary",
]

class WorkPreferences(BaseModel):
    remote: bool = False
    full_time: bool = True
    freelance: bool = False
    work_location_preference: Literal["local", "abroad", "both"] = "local"

class MarketAgentInput(BaseModel):
    user_id: str

    query: str

    target_roles: list[str]

    skills: list[str]

    experience_years: int

    preferred_locations: list[str]

    work_preferences: WorkPreferences


class PlannerOutput(BaseModel):
    market_modes: list[MarketMode]

    role_queries: list[str]

    locations: list[str]

    skills: list[str]


class Source(BaseModel):
    name: str

    url: HttpUrl

    retrieved_at: datetime


class JobPosting(BaseModel):
    title: str

    company: str

    location: str

    description: str | None = None

    source: Source

    confidence: float = Field(ge=0.0, le=1.0)


class SalaryInsight(BaseModel):
    role: str

    location: str

    min_salary: float | None = None

    max_salary: float | None = None

    currency: str

    source: Source

    confidence: float = Field(ge=0.0, le=1.0)


class MarketTrend(BaseModel):
    insight: str

    related_skills: list[str]

    source: Source

    confidence: float = Field(ge=0.0, le=1.0)


class SkillGap(BaseModel):
    skill: str

    importance: Literal["low", "medium", "high"]

    reason: str
    market: MarketMode

class MarketAgentOutput(BaseModel):
    job_postings: list[JobPosting]

    salary_insights: list[SalaryInsight]

    market_trends: list[MarketTrend]

    skill_gaps: list[SkillGap]



class LaneQuery(BaseModel):
    lane: LaneType
    market_mode: MarketMode
    role: str
    location: str | None = None