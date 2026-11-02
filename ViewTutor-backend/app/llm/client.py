"""OpenAI client: exactly one API call per request, never raises.

Uses the Responses API with a strict JSON schema (structured output). SDK
retries are disabled (`max_retries=0`), so a failure is reported, logged and
answered with a fallback instead of being retried silently.

Failure kinds:
  timeout            the call exceeded LLM_TIMEOUT_S
  api_error          any API or connection error (incl. a model that rejects the schema)
  refusal            the model refused
  incomplete_output  the response stopped early (e.g. max_output_tokens)
  invalid_output     the text is not JSON with a non-empty "tutor_text" string
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional, Protocol

from app.config import Settings
from app.llm.prompts import Prompt

FailureKind = Literal["timeout", "api_error", "refusal", "incomplete_output", "invalid_output"]

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"tutor_text": {"type": "string"}},
    "required": ["tutor_text"],
    "additionalProperties": False,
}


@dataclass
class LLMResult:
    """Outcome of one generation attempt. `text` is set only on success."""

    text: Optional[str] = None
    failure: Optional[FailureKind] = None
    failure_detail: Optional[str] = None
    raw_output: Optional[str] = None
    model: Optional[str] = None
    response_id: Optional[str] = None
    api_latency_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.text is not None

    def to_log(self) -> dict[str, Any]:
        return asdict(self)


class LLMClient(Protocol):
    def generate(self, prompt: Prompt) -> LLMResult: ...


def parse_output(raw: str) -> tuple[Optional[str], Optional[str]]:
    """Return (tutor_text, None) or (None, reason) for structured output text."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None, "not_json"
    if not isinstance(data, dict):
        return None, "not_object"
    text = data.get("tutor_text")
    if not isinstance(text, str):
        return None, "tutor_text_missing"
    text = " ".join(text.split())
    if not text:
        return None, "tutor_text_empty"
    return text, None


def _generation_settings(settings: Settings) -> dict[str, Any]:
    """Every generation setting, logged with each call (never the key)."""
    return {
        "provider": "openai",
        "model": settings.llm_model,
        "reasoning_effort": settings.llm_reasoning_effort or None,
        "max_output_tokens": settings.llm_max_output_tokens,
        "timeout_s": settings.llm_timeout_s,
        "max_retries": 0,
        "structured_output": "json_schema_strict",
    }


class OpenAIClient:
    """Real client. Created only when USE_MOCK_LLM is off and a key is set."""

    def __init__(self, settings: Settings, sdk_client: Any = None):
        self.settings = settings
        if sdk_client is None:
            import openai

            sdk_client = openai.OpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.llm_timeout_s,
                max_retries=0,
            )
        self._client = sdk_client

    def generate(self, prompt: Prompt) -> LLMResult:
        import openai

        result = LLMResult(model=self.settings.llm_model, settings=_generation_settings(self.settings))
        kwargs: dict[str, Any] = {
            "model": self.settings.llm_model,
            "instructions": prompt.instructions,
            "input": prompt.payload,
            "max_output_tokens": self.settings.llm_max_output_tokens,
            "text": {"format": {"type": "json_schema", "name": "tutor_reply",
                                "schema": OUTPUT_SCHEMA, "strict": True}},
            "store": False,
        }
        if self.settings.llm_reasoning_effort:
            kwargs["reasoning"] = {"effort": self.settings.llm_reasoning_effort}

        start = time.perf_counter()
        try:
            response = self._client.responses.create(**kwargs)
        except openai.APITimeoutError as exc:
            result.api_latency_ms = (time.perf_counter() - start) * 1000
            result.failure, result.failure_detail = "timeout", type(exc).__name__
            return result
        except Exception as exc:  # any SDK, HTTP or connection error
            result.api_latency_ms = (time.perf_counter() - start) * 1000
            status = getattr(exc, "status_code", None)
            result.failure = "api_error"
            result.failure_detail = f"{type(exc).__name__}" + (f" (HTTP {status})" if status else "")
            return result
        result.api_latency_ms = (time.perf_counter() - start) * 1000
        return self._read(response, result)

    @staticmethod
    def _read(response: Any, result: LLMResult) -> LLMResult:
        """Turn an SDK response into an LLMResult. Never raises."""
        try:
            result.response_id = getattr(response, "id", None)
            result.model = getattr(response, "model", None) or result.model
            usage = getattr(response, "usage", None)
            if usage is not None:
                result.input_tokens = getattr(usage, "input_tokens", None)
                result.output_tokens = getattr(usage, "output_tokens", None)
                details = getattr(usage, "output_tokens_details", None)
                result.reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None

            for item in getattr(response, "output", None) or []:
                if getattr(item, "type", None) == "message":
                    for content in getattr(item, "content", None) or []:
                        if getattr(content, "type", None) == "refusal":
                            result.failure = "refusal"
                            result.failure_detail = (getattr(content, "refusal", "") or "")[:300]
                            return result

            status = getattr(response, "status", None)
            if status != "completed":
                details = getattr(response, "incomplete_details", None)
                reason = getattr(details, "reason", None) if details else None
                result.failure = "incomplete_output"
                result.failure_detail = f"status={status}" + (f", reason={reason}" if reason else "")
                result.raw_output = getattr(response, "output_text", None)
                return result

            raw = getattr(response, "output_text", "") or ""
            result.raw_output = raw
            text, problem = parse_output(raw)
            if text is None:
                result.failure, result.failure_detail = "invalid_output", problem
                return result
            result.text = text
            return result
        except Exception as exc:  # defensive
            result.failure, result.failure_detail = "invalid_output", f"read_error:{type(exc).__name__}"
            return result
