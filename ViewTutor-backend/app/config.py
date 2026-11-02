"""Runtime settings, read once from environment variables.

The API key is read from the environment only. It is never written to logs,
responses or files by this application.
"""
from __future__ import annotations

import os
import math
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

APP_VERSION = "1.0.0-step1"
QUESTIONS_FILE = PROJECT_DIR / "data" / "questions.json"


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a whole number, got {value!r}") from exc


@dataclass(frozen=True)
class Settings:
    """All configurable values. Logged (except the key) with every request."""

    openai_api_key: str = field(repr=False, default="")
    llm_model: str = "gpt-6.1-sol"
    llm_reasoning_effort: str = "low"
    llm_timeout_s: int = 20
    llm_max_output_tokens: int = 400
    use_mock_llm: bool = True
    prompt_version: str = "step1-v2"
    log_dir: Path = PROJECT_DIR / "logs"
    pov_visibility_low: float = 0.10
    pov_visibility_high: float = 0.70

    def __post_init__(self) -> None:
        low, high = self.pov_visibility_low, self.pov_visibility_high
        if not (math.isfinite(low) and math.isfinite(high) and 0 <= low < high <= 1):
            raise ValueError("POV visibility thresholds must satisfy 0 <= low < high <= 1")

    @property
    def llm_configured(self) -> bool:
        """True when the tutor can produce hints: mock mode, or a key is present."""
        return self.use_mock_llm or bool(self.openai_api_key)

    @property
    def provider(self) -> str:
        return "mock" if self.use_mock_llm else "openai"

    @property
    def model_id(self) -> str:
        return "mock" if self.use_mock_llm else self.llm_model


def load_settings() -> Settings:
    """Build settings from the environment. Missing values use safe defaults."""
    log_dir = Path(os.getenv("LOG_DIR") or "logs")
    if not log_dir.is_absolute():
        log_dir = PROJECT_DIR / log_dir
    return Settings(
        openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip(),
        llm_model=(os.getenv("LLM_MODEL") or "gpt-6.1-sol").strip(),
        llm_reasoning_effort=(os.getenv("LLM_REASONING_EFFORT") or "low").strip(),
        llm_timeout_s=_env_int("LLM_TIMEOUT_S", 20),
        llm_max_output_tokens=_env_int("LLM_MAX_OUTPUT_TOKENS", 400),
        use_mock_llm=_env_flag("USE_MOCK_LLM", True),
        prompt_version=(os.getenv("PROMPT_VERSION") or "step1-v2").strip(),
        log_dir=log_dir,
        pov_visibility_low=float(os.getenv("POV_VISIBILITY_LOW", "0.10")),
        pov_visibility_high=float(os.getenv("POV_VISIBILITY_HIGH", "0.70")),
    )
