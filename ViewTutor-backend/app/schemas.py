"""Request and response formats.

The field names and allowed values match the Unity client exactly
(`Networking/DTOs/*.cs`, Newtonsoft.Json, snake_case). Unity throws if a
response is missing, empty or has an enum value it does not know, so every
value the backend returns must come from the sets defined here.

Fields that Unity does not send today (`view`, `request_id`) are optional.
Existing Unity requests validate unchanged.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Support types accepted by v4 (`schemas.SupportType`). Unity currently sends
# AUTO_CHECK, CHECK_WORK, HINT and SIMPLIFY_STORY; the rest stay accepted.
SupportType = Literal[
    "AUTO_CHECK",
    "SIMPLIFY_STORY",
    "INTERFACE_HELP",
    "CHECK_WORK",
    "SMALLER_EXAMPLE",
    "UNSURE",
    "HINT",
    "OPEN_ENDED",
]
SUPPORT_TYPES: tuple[str, ...] = SupportType.__args__  # type: ignore[attr-defined]
DEFAULT_SUPPORT_TYPE = "AUTO_CHECK"

# Listed in /api/health exactly as v4 listed them.
HEALTH_SUPPORT_OPTIONS: list[str] = ["SIMPLIFY_STORY", "CHECK_WORK", "HINT", "OPEN_ENDED"]

ConversationStatus = Literal["continue", "correct"]

# How a request ended. Logged with every request and returned to Unity as an
# extra field (Unity ignores unknown fields).
DecisionStatus = Literal[
    "confirmed_correct",     # evaluator says correct; fixed confirmation, no LLM call
    "generated",             # LLM text passed answer protection and was returned
    "fallback_llm_error",    # LLM failed (refusal, incomplete, timeout, API or output error)
    "fallback_blocked",      # LLM text was blocked by answer protection
    "request_rejected",      # layer 1: malformed request or unknown question
    "workspace_rejected",    # layer 2: impossible learner state
    "internal_error",        # unexpected exception; neutral message returned by the middleware
]


# --------------------------------------------------------------------------
# Request
# --------------------------------------------------------------------------

class ConversationMessage(BaseModel):
    """One turn of history. Roles as in v4."""

    model_config = ConfigDict(extra="ignore")
    role: Literal["student", "tutor"]
    content: str


class RegionView(BaseModel):
    """What the learner can see of one workspace region. Not used in Step 1."""

    model_config = ConfigDict(extra="ignore")
    region_id: Optional[str] = None
    visible_fraction: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    label_visible: Optional[bool] = None
    label_seen_this_attempt: Optional[bool] = None


class ViewData(BaseModel):
    """Learner point of view. Optional and nullable; accepted and logged only.

    Step 1 never uses this block for tutoring.
    """

    model_config = ConfigDict(extra="ignore")
    timestamp_ms: Optional[int] = None
    gaze_target: Optional[str] = None
    head_position: Optional[list[float]] = None
    head_forward: Optional[list[float]] = None
    fov_deg: Optional[list[float]] = None
    regions: Optional[list[RegionView]] = None
    last_touched_region_id: Optional[str] = None
    attempt_id: Optional[str] = None
    snapshot_source: Optional[str] = None
    snapshot_age_ms: Optional[int] = Field(default=None, ge=0)


class TutorRequest(BaseModel):
    """Body of POST /api/tutor (Unity `TutorRequestDto`).

    Free-text fields are normalized (null → "", over-long text truncated) by
    `validation.validate_request` before this model is built, so a long
    `latest_action` never causes a rejection.
    """

    model_config = ConfigDict(extra="ignore")
    question_id: str = Field(min_length=1)
    learner_state: dict[str, Any]
    support_type: SupportType = DEFAULT_SUPPORT_TYPE
    latest_action: str = ""
    student_message: str = ""
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    # Optional additions; absent in today's Unity requests.
    request_id: Optional[str] = None
    view: Optional[ViewData] = None


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------

class TutorResponse(BaseModel):
    """Body returned by POST /api/tutor (Unity `TutorResponseDto` + extras).

    Unity reads the first four fields. The rest are for logging and debugging.
    """

    tutor_response: str = Field(min_length=1)
    conversation_status: ConversationStatus
    student_correct: bool
    support_type: SupportType
    # Extras (ignored by Unity)
    status: DecisionStatus
    request_id: str
    model: Optional[str] = None
    api_latency_ms: Optional[float] = None
    total_latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Body of GET /api/health (Unity `HealthResponseDto`).

    The local-model fields are kept so the Unity DTO still parses; they carry
    neutral values because this backend uses a hosted API.
    """

    status: str
    app_version: str
    question_count: int
    support_options: list[str]
    llm_provider: str
    llm_model: Optional[str]
    llm_configured: bool
    llm_loaded: bool
    hf_token_configured: bool = False
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    load_in_4bit: bool = False
    model_error: Optional[str] = None
    model_load_attempted: bool = False
    # Extras (ignored by Unity): research-log health.
    log_storage_ok: Optional[bool] = None
    log_write_failures: int = 0
    log_storage_error: Optional[str] = None
