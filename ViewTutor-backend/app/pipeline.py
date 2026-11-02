"""The /api/tutor pipeline: one tutor response per request, at most one LLM call.

    layer 1 (request) → layer 2 (workspace) → evaluator
      → correct?  fixed confirmation, no LLM call
      → else      prompt → LLM (one call) → answer protection
                  → pass: LLM text        (status "generated")
                  → fail: checked fallback ("fallback_blocked" / "fallback_llm_error")

Every step adds its results to the request's `RequestRecord`. This module never
writes the final log record; the middleware does.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from app.answer_protection import _is_interface_message, check_response
from app.config import APP_VERSION, Settings
from app.evaluator import evaluate
from app.fallback import NEUTRAL_MESSAGE, Fallback, choose_fallback, confirmation
from app.llm.client import LLMClient, LLMResult
from app.llm.prompts import build_prompt
from app.pov_context import build_pov_context
from app.research_log import RequestRecord
from app.schemas import DEFAULT_SUPPORT_TYPE, SUPPORT_TYPES, TutorResponse
from app.strategies import strategy_context
from app.validation import validate_request, validate_workspace


def echo_support_type(raw: Any) -> str:
    """The support_type to return to Unity: the request's if valid, else AUTO_CHECK."""
    if isinstance(raw, dict) and raw.get("support_type") in SUPPORT_TYPES:
        return raw["support_type"]
    return DEFAULT_SUPPORT_TYPE


def neutral_response(record: RequestRecord, status: str, support_type: str) -> TutorResponse:
    """Fixed, hint-free response when the request or state cannot be used."""
    record.add(status=status, final_text=NEUTRAL_MESSAGE, student_correct=False,
               conversation_status="continue", response_support_type=support_type)
    return TutorResponse(
        tutor_response=NEUTRAL_MESSAGE, conversation_status="continue", student_correct=False,
        support_type=support_type, status=status, request_id=record.request_id,
        total_latency_ms=round(record.elapsed_ms(), 1),
    )


def _log_fallback(record: RequestRecord, fallback: Fallback) -> None:
    record.add(fallback_source=fallback.source, fallback_passed_checks=fallback.passed_checks,
               fallback_first_failed_rule=fallback.first_failed_rule)


def handle_tutor(raw: Any, record: RequestRecord, settings: Settings,
                 client: Optional[LLMClient], question_by_id: Mapping[str, dict], *,
                 condition: str = "baseline") -> TutorResponse:
    """Run the pipeline for one parsed JSON body."""
    if condition not in ("baseline", "pov_aware"):
        raise ValueError(f"invalid tutor condition: {condition!r}")
    record.add(tutor_condition=condition)
    support_echo = echo_support_type(raw)
    record.add(app_version=APP_VERSION, prompt_version=settings.prompt_version,
               provider=settings.provider, model=settings.model_id,
               support_type_echo=support_echo, raw_request=raw)

    # Layer 1 -------------------------------------------------------------------
    checked = validate_request(raw, question_by_id)
    record.add(request_warnings=checked.warnings)
    if not checked.ok:
        record.add(rejection_reason=checked.reason)
        return neutral_response(record, "request_rejected", support_echo)
    request, question = checked.request, checked.question
    record.add(question_id=question["id"], interaction=question["interaction"],
               support_type=request.support_type, client_request_id=request.request_id,
               view=request.view.model_dump() if request.view else None)

    # Layer 2 -------------------------------------------------------------------
    workspace_check = validate_workspace(question, request.learner_state)
    record.add(workspace_warnings=workspace_check.warnings)
    if not workspace_check.ok:
        record.add(rejection_reason=workspace_check.reason)
        return neutral_response(record, "workspace_rejected", request.support_type)

    # Evaluator -----------------------------------------------------------------
    evaluation = evaluate(question, workspace_check.workspace)
    facts = dict(evaluation.facts)
    record.add(construction_status=evaluation.construction_status, construction_errors=list(evaluation.errors),
               construction_notes=list(evaluation.notes),
               answer_entered=evaluation.answer_entered, answer_parseable=evaluation.answer_parseable,
               answer_correct=evaluation.answer_correct, student_correct=evaluation.student_correct,
               conversation_status=evaluation.conversation_status)

    # v4: an interface question typed by the learner is answered as INTERFACE_HELP.
    effective = request
    if request.student_message.strip() and _is_interface_message(request.student_message):
        effective = request.model_copy(update={"support_type": "INTERFACE_HELP"})
    record.add(effective_support_type=effective.support_type)
    context = strategy_context(question, facts, effective.support_type)

    pov_context = None
    pov_warnings = []
    if condition == "pov_aware":
        pov_context, pov_warnings = build_pov_context(
            question, request.view,
            low=settings.pov_visibility_low,
            high=settings.pov_visibility_high,
            learner_state=request.learner_state,
        )
    record.add(pov_context=pov_context, pov_warnings=pov_warnings,
               pov_used=pov_context is not None,
               pov_visibility_thresholds={"low": settings.pov_visibility_low,
                                          "high": settings.pov_visibility_high})

    llm: Optional[LLMResult] = None
    if evaluation.student_correct:
        chosen = confirmation(question, effective, facts, context)
        _log_fallback(record, chosen)
        text, status = chosen.text, "confirmed_correct"
        record.add(llm_called=False)
    else:
        prompt = build_prompt(question, effective, evaluation, context, settings.prompt_version,
                              pov_context=pov_context)
        record.add(llm_called=True, prompt_instructions=prompt.instructions, prompt_payload=prompt.payload)
        if client is None:
            llm = LLMResult(failure="api_error", failure_detail="llm_not_configured")
        else:
            try:
                llm = client.generate(prompt)
            except Exception as exc:  # a broken client must not break the response
                llm = LLMResult(failure="api_error", failure_detail=f"client_exception:{type(exc).__name__}")
        record.event("llm_result", **llm.to_log())
        record.add(llm_ok=llm.ok, llm_failure=llm.failure, llm_failure_detail=llm.failure_detail,
                   llm_raw_output=llm.raw_output, llm_model=llm.model, llm_response_id=llm.response_id,
                   llm_settings=llm.settings, api_latency_ms=llm.api_latency_ms,
                   input_tokens=llm.input_tokens, output_tokens=llm.output_tokens,
                   reasoning_tokens=llm.reasoning_tokens)

        if llm.ok:
            rule = check_response(llm.text, question, effective, facts, context)
            record.add(protection_rule=rule, llm_text=llm.text)
            if rule is None:
                text, status = llm.text, "generated"
            else:
                record.event("blocked_by_answer_protection", rule=rule, text=llm.text)
                chosen = choose_fallback(question, effective, facts, context, pov_context=pov_context)
                _log_fallback(record, chosen)
                text, status = chosen.text, "fallback_blocked"
        else:
            chosen = choose_fallback(question, effective, facts, context, pov_context=pov_context)
            _log_fallback(record, chosen)
            text, status = chosen.text, "fallback_llm_error"

    record.add(status=status, final_text=text, response_support_type=request.support_type)
    return TutorResponse(
        tutor_response=text,
        conversation_status=evaluation.conversation_status,
        student_correct=evaluation.student_correct,
        support_type=request.support_type,
        status=status,
        request_id=record.request_id,
        model=llm.model if llm else None,
        api_latency_ms=round(llm.api_latency_ms, 1) if llm and llm.api_latency_ms is not None else None,
        total_latency_ms=round(record.elapsed_ms(), 1),
    )
