"""FastAPI app: the endpoints Unity calls.

/api/tutor guarantees:
- HTTP 200 with all four Unity fields for every request: malformed JSON, invalid
  requests, impossible states, LLM failures and unexpected exceptions included.
- Exactly one final research-log record per request, written only by the
  `tutor_logging` middleware.

Run:  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import APP_VERSION, Settings, load_settings
from app.fallback import NEUTRAL_MESSAGE
from app.llm.client import LLMClient, OpenAIClient
from app.llm.mock_client import MockClient
from app.pipeline import echo_support_type, handle_tutor, neutral_response
from app.questions import QUESTION_BY_ID, QUESTIONS, STUDENT_QUESTIONS
from app import research_log
from app.research_log import RequestRecord, storage_check
from app.schemas import DEFAULT_SUPPORT_TYPE, HEALTH_SUPPORT_OPTIONS, HealthResponse

TUTOR_PATH = "/api/tutor"


def build_health(settings: Settings) -> HealthResponse:
    """Health payload with every field Unity's HealthResponseDto expects."""
    model_error: Optional[str] = None
    storage_ok, storage_error = storage_check(settings.log_dir)
    if not settings.llm_configured:
        model_error = "OPENAI_API_KEY is not set and USE_MOCK_LLM is off."
    return HealthResponse(
        status="ok",
        app_version=APP_VERSION,
        question_count=len(QUESTIONS),
        support_options=list(HEALTH_SUPPORT_OPTIONS),
        llm_provider=settings.provider,
        llm_model=settings.model_id,
        llm_configured=settings.llm_configured,
        llm_loaded=settings.llm_configured,
        model_error=model_error,
        log_storage_ok=storage_ok,
        log_write_failures=research_log.WRITE_FAILURES,
        log_storage_error=storage_error or research_log.LAST_WRITE_ERROR,
    )


def build_client(settings: Settings) -> Optional[LLMClient]:
    """Mock by default; OpenAI only when explicitly enabled with a key."""
    if settings.use_mock_llm:
        return MockClient()
    if settings.openai_api_key:
        return OpenAIClient(settings)
    return None  # requests then get a logged fallback (llm_not_configured)


def _emergency_body(record: RequestRecord) -> dict[str, Any]:
    """Built without pydantic so it cannot fail. Always Unity-parseable."""
    support_type = record.fields.get("support_type_echo") or DEFAULT_SUPPORT_TYPE
    record.add(status="internal_error", final_text=NEUTRAL_MESSAGE, student_correct=False,
               conversation_status="continue", response_support_type=support_type)
    return {
        "tutor_response": NEUTRAL_MESSAGE,
        "conversation_status": "continue",
        "student_correct": False,
        "support_type": support_type,
        "status": "internal_error",
        "request_id": record.request_id,
        "model": None,
        "api_latency_ms": None,
        "total_latency_ms": round(record.elapsed_ms(), 1),
    }


def _capture_raw_request(body: bytes) -> None:
    """Optional: save each raw request body when CAPTURE_REQUESTS_DIR is set.

    For checking what Unity really sends (see CAPTURE_GUIDE.md). Off by default.
    The files contain learner state, so keep them private. Never raises.
    """
    folder = os.environ.get("CAPTURE_REQUESTS_DIR", "").strip()
    if not folder:
        return
    try:
        from datetime import datetime, timezone
        from pathlib import Path
        target = Path(folder)
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        (target / f"request-{stamp}.json").write_bytes(body)
    except Exception:  # noqa: BLE001 - capturing must never break tutoring
        pass


def create_app(settings: Optional[Settings] = None, client: Optional[LLMClient] = None,
               use_default_client: bool = True) -> FastAPI:
    """Build the app. Tests pass their own settings and client."""
    settings = settings or load_settings()
    ok, error = storage_check(settings.log_dir)
    if not ok:  # do not stop the server (Unity needs it), but say so loudly
        print(f"WARNING: research log storage not writable: {error}", file=sys.stderr)
    if client is None and use_default_client:
        client = build_client(settings)
    app = FastAPI(title="MathConstructVR Tutor Backend", version=APP_VERSION)
    app.state.settings = settings
    app.state.client = client

    @app.middleware("http")
    async def tutor_logging(request: Request, call_next):
        """The only writer of the final log record for /api/tutor."""
        if request.url.path != TUTOR_PATH:
            return await call_next(request)
        record = RequestRecord(settings.log_dir)
        request.state.record = record
        try:
            response = await call_next(request)
            if response.status_code != 200:
                # e.g. a GET to /api/tutor; Unity must still get a parseable 200.
                record.add(upstream_http_status=response.status_code)
                response = JSONResponse(_emergency_body(record), status_code=200)
        except Exception as exc:
            record.add(exception=f"{type(exc).__name__}: {exc}"[:500])
            response = JSONResponse(_emergency_body(record), status_code=200)
        finally:
            record.add(http_status=200)
            logged = record.finalize()
        # Visible signal when the final record could not be written.
        response.headers["X-Research-Log"] = "ok" if logged else "failed"
        return response

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return build_health(settings)

    @app.get("/api/questions")
    def questions() -> list[dict[str, Any]]:
        """All questions with hidden quantities removed (never empty)."""
        return STUDENT_QUESTIONS

    @app.post(TUTOR_PATH)
    async def tutor(request: Request) -> JSONResponse:
        """Reads the raw body itself so FastAPI never answers 422."""
        record: RequestRecord = request.state.record
        body = await request.body()
        try:
            raw = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            record.add(rejection_reason="malformed_json", raw_body_bytes=len(body))
            response = neutral_response(record, "request_rejected", DEFAULT_SUPPORT_TYPE)
        else:
            # Recorded first, so even an early crash echoes the request's support type.
            record.add(support_type_echo=echo_support_type(raw))
            _capture_raw_request(body)
            response = handle_tutor(raw, record, settings, client, QUESTION_BY_ID)
        return JSONResponse(json.loads(response.model_dump_json()))

    return app


app = create_app()
