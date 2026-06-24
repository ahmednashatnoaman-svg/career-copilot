from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentMode = Literal["auto", "mock_interview", "career_plan", "general_advice"]


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    current_role: str | None = None
    target_role: str | None = None
    experience_level: str | None = None
    skills: list[str] = Field(default_factory=list)
    career_goal: str | None = None


class ChatRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1)
    thread_id: str = Field(default="demo_thread", min_length=1)
    message: str = Field(min_length=1)
    mode: AgentMode = "auto"
    profile: UserProfile = Field(default_factory=UserProfile)
    max_interview_questions: int = Field(default=5, ge=1, le=15)


class ChatResponse(BaseModel):
    agent: str = "career_coaching_agent"
    request_id: str | None = None
    user_id: str
    thread_id: str
    sub_intent: str
    response: str
    next_action: str
    state: dict[str, Any] = Field(default_factory=dict)
    memory_updates: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)


class SessionResetRequest(BaseModel):
    user_id: str = Field(default="demo_user", min_length=1)
    thread_id: str = Field(default="demo_thread", min_length=1)


class SessionResetResponse(BaseModel):
    status: Literal["ok"]
    request_id: str | None = None
    user_id: str
    thread_id: str
    deleted: dict[str, int] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    agent_ready: bool
    llm_configured: bool
    langsmith_tracing: bool = False
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: dict[str, Any]
