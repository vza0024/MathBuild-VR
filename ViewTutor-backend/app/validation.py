"""Layers 1 and 2 of validation. Neither function ever raises.

Layer 1 — `validate_request`: is the request well formed, and does the question
exist? Free-text fields are normalized instead of rejected, so tutoring is
never blocked by text length, a malformed history turn or a malformed view.

Layer 2 — `validate_workspace`: is the learner state possible for this
question's interaction type? Counts must be whole numbers >= 0, except JOIN
`added_count`, which is a difference and may be negative. Number parsing
follows v4 (`evaluator.int_or_none`, `evaluator.answer_entry`), so any state v4
accepted with present fields is accepted here.

A rejection is reported as a reason string; the caller turns it into a safe
200 response (Unity cannot handle HTTP errors).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional

from pydantic import ValidationError

from app.schemas import (
    SUPPORT_TYPES,
    ConversationMessage,
    TutorRequest,
    ViewData,
)

# Text limits. Longer text is truncated, never rejected.
MAX_LATEST_ACTION = 1000
MAX_STUDENT_MESSAGE = 400
MAX_HISTORY_CONTENT = 1200
MAX_HISTORY_TURNS = 30

# Sanity limits for workspace values. Anything above is treated as corrupt.
MAX_COUNT = 1000
MAX_REGIONS = 50


# --------------------------------------------------------------------------
# Layer 1: request
# --------------------------------------------------------------------------

@dataclass
class RequestValidation:
    """Result of layer 1. Exactly one of `request` / `reason` is set."""

    request: Optional[TutorRequest] = None
    question: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.request is not None


def _text(value: Any, name: str, limit: int, warnings: list[str]) -> str:
    """Normalize a free-text field: None → "", non-string → str, truncate."""
    if value is None:
        return ""
    if not isinstance(value, str):
        warnings.append(f"{name}_not_string")
        value = str(value)
    if len(value) > limit:
        warnings.append(f"{name}_truncated")
        value = value[:limit]
    return value


def _history(value: Any, warnings: list[str]) -> list[dict[str, str]]:
    """Keep valid turns, drop the rest, keep the most recent MAX_HISTORY_TURNS."""
    if value is None:
        return []
    if not isinstance(value, list):
        warnings.append("conversation_history_not_list")
        return []
    kept: list[dict[str, str]] = []
    for turn in value:
        try:
            message = ConversationMessage.model_validate(turn)
        except ValidationError:
            warnings.append("conversation_history_turn_dropped")
            continue
        content = message.content.strip()
        if not content:
            warnings.append("conversation_history_turn_dropped")
            continue
        if len(content) > MAX_HISTORY_CONTENT:
            warnings.append("conversation_history_turn_truncated")
            content = content[:MAX_HISTORY_CONTENT]
        kept.append({"role": message.role, "content": content})
    if len(kept) > MAX_HISTORY_TURNS:
        warnings.append("conversation_history_shortened")
        kept = kept[-MAX_HISTORY_TURNS:]
    return kept


def _view(value: Any, warnings: list[str]) -> Optional[dict[str, Any]]:
    """Accept a valid view, drop an invalid one. Step 1 only logs it."""
    if value is None:
        return None
    try:
        return ViewData.model_validate(value).model_dump()
    except ValidationError:
        warnings.append("view_invalid_dropped")
        return None


def validate_request(raw: Any, question_by_id: Mapping[str, dict[str, Any]]) -> RequestValidation:
    """Layer 1. Check the request shape and that the question exists."""
    try:
        return _validate_request(raw, question_by_id)
    except Exception as exc:  # defensive: layer 1 must never raise
        return RequestValidation(reason=f"request_check_error:{type(exc).__name__}")


def _validate_request(raw: Any, question_by_id: Mapping[str, dict[str, Any]]) -> RequestValidation:
    warnings: list[str] = []
    if not isinstance(raw, dict):
        return RequestValidation(reason="body_not_object")

    question_id = raw.get("question_id")
    if not isinstance(question_id, str) or not question_id.strip():
        return RequestValidation(reason="question_id_missing")
    question = question_by_id.get(question_id)
    if question is None:
        return RequestValidation(reason="question_id_unknown")

    learner_state = raw.get("learner_state")
    if not isinstance(learner_state, dict):
        return RequestValidation(reason="learner_state_not_object")

    support_type = raw.get("support_type")
    if support_type is None:
        support_type = "AUTO_CHECK"
        warnings.append("support_type_defaulted")
    if support_type not in SUPPORT_TYPES:
        return RequestValidation(reason="support_type_unknown")

    request_id = raw.get("request_id")
    if request_id is not None and not isinstance(request_id, str):
        warnings.append("request_id_ignored")
        request_id = None

    cleaned = {
        "question_id": question_id,
        "learner_state": learner_state,
        "support_type": support_type,
        "latest_action": _text(raw.get("latest_action"), "latest_action", MAX_LATEST_ACTION, warnings),
        "student_message": _text(raw.get("student_message"), "student_message", MAX_STUDENT_MESSAGE, warnings),
        "conversation_history": _history(raw.get("conversation_history"), warnings),
        "request_id": request_id,
        "view": _view(raw.get("view"), warnings),
    }
    try:
        request = TutorRequest.model_validate(cleaned)
    except ValidationError as exc:  # should be unreachable after cleaning
        return RequestValidation(reason=f"schema_error:{exc.errors()[0].get('type', 'unknown')}")
    return RequestValidation(request=request, question=question, warnings=warnings)


# --------------------------------------------------------------------------
# Layer 2: workspace
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Workspace:
    """A learner state that passed layer 2.

    `values` holds the parsed counts for the interaction type (lists become
    tuples). `answer` is the entered number, or None if blank.
    `answer_invalid` is True when something non-numeric was entered (v4 rule:
    counted as an entered answer that cannot be supported).
    """

    interaction: str
    values: Mapping[str, Any]
    answer: Optional[int]
    answer_invalid: bool


@dataclass
class WorkspaceValidation:
    workspace: Optional[Workspace] = None
    reason: Optional[str] = None
    # Non-blocking observations, e.g. a count total that differs from the story.
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.workspace is not None


# Required count fields per interaction (non-nullable ints in the Unity DTOs).
_REQUIRED_COUNTS: dict[str, tuple[str, ...]] = {
    "JOIN": ("added_count", "current_count"),
    "REMOVE": ("removed_count", "remaining_count"),
    "EQUAL_GROUPS": ("undistributed_count",),
    "EQUAL_SHARING": ("undistributed_count",),
    "PART_TO_PART_RATIO": ("part_a_count", "part_b_count", "unassigned_a", "unassigned_b"),
}
# Required list fields per interaction.
_REQUIRED_LISTS: dict[str, tuple[str, ...]] = {
    "EQUAL_GROUPS": ("group_sizes",),
    "EQUAL_SHARING": ("share_sizes",),
}
# Optional JOIN fields from the newer physical-construction state; parsed if present.
_OPTIONAL_JOIN_COUNTS: tuple[str, ...] = ("part_a_count", "part_b_count", "total_count")

# Fields that are differences, not physical counts, and may be negative.
# JOIN `added_count` is computed by Unity as current_count minus the starting
# amount; it goes below zero when the learner moves starting objects out
# (seen in 5 of the 145 logged Unity requests). v4 accepted these.
_SIGNED_FIELDS: dict[str, frozenset[str]] = {
    "JOIN": frozenset({"added_count"}),
}


def parse_whole_number(value: Any) -> Optional[int]:
    """v4 `int_or_none`: whole number or None. Bools and fractions are rejected."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else None


def parse_answer(value: Any) -> tuple[Optional[int], bool]:
    """v4 `answer_entry`: (parsed answer, something unparsable was entered)."""
    if value is None or value == "":
        return None, False
    parsed = parse_whole_number(value)
    return parsed, parsed is None


def _count(
    state: Mapping[str, Any], name: str, signed: bool = False
) -> tuple[Optional[int], Optional[str]]:
    if name not in state or state[name] is None:
        return None, f"{name}_missing"
    number = parse_whole_number(state[name])
    if number is None:
        return None, f"{name}_not_whole_number"
    if number < 0 and not signed:
        return None, f"{name}_negative"
    if abs(number) > MAX_COUNT:
        return None, f"{name}_too_large"
    return number, None


def _count_list(state: Mapping[str, Any], name: str) -> tuple[Optional[tuple[int, ...]], Optional[str]]:
    values = state.get(name)
    if values is None:
        return None, f"{name}_missing"
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        return None, f"{name}_not_list"
    if len(values) > MAX_REGIONS:
        return None, f"{name}_too_long"
    parsed: list[int] = []
    for value in values:
        number = parse_whole_number(value)
        if number is None:
            return None, f"{name}_not_whole_numbers"
        if number < 0:
            return None, f"{name}_negative"
        if number > MAX_COUNT:
            return None, f"{name}_too_large"
        parsed.append(number)
    return tuple(parsed), None


def conservation_warnings(question: Mapping[str, Any], values: Mapping[str, Any]) -> list[str]:
    """Counts that should add up to a fixed story quantity but do not.

    In every logged Unity request, REMOVE (removed + remaining = initial),
    EQUAL_SHARING (shares + bank = total) and RATIO (placed + unassigned = each
    part) kept these totals fixed. EQUAL_GROUPS does not (the printer tray adds
    objects) and JOIN is not checked. A mismatch is logged as a warning, not
    rejected: it points to a Unity bug or a new workspace mode, and the child
    should still get tutoring.
    """
    p = question.get("parameters") or {}
    interaction = question.get("interaction")
    warnings: list[str] = []
    if interaction == "REMOVE":
        if values["removed_count"] + values["remaining_count"] != p.get("initial"):
            warnings.append("remove_total_differs_from_initial")
    elif interaction == "EQUAL_SHARING":
        if sum(values["share_sizes"]) + values["undistributed_count"] != p.get("total"):
            warnings.append("sharing_total_differs_from_story")
    elif interaction == "PART_TO_PART_RATIO":
        if values["part_a_count"] + values["unassigned_a"] != p.get("part_a"):
            warnings.append("ratio_part_a_total_differs_from_story")
        if values["part_b_count"] + values["unassigned_b"] != p.get("part_b"):
            warnings.append("ratio_part_b_total_differs_from_story")
    return warnings


def validate_workspace(question: Mapping[str, Any], learner_state: Mapping[str, Any]) -> WorkspaceValidation:
    """Layer 2. Check the learner state for the question's interaction type."""
    try:
        interaction = question["interaction"]
        values: dict[str, Any] = {}
        signed = _SIGNED_FIELDS.get(interaction, frozenset())

        for name in _REQUIRED_COUNTS[interaction]:
            number, reason = _count(learner_state, name, signed=name in signed)
            if reason:
                return WorkspaceValidation(reason=reason)
            values[name] = number

        for name in _REQUIRED_LISTS.get(interaction, ()):
            numbers, reason = _count_list(learner_state, name)
            if reason:
                return WorkspaceValidation(reason=reason)
            values[name] = numbers

        if interaction == "JOIN":
            for name in _OPTIONAL_JOIN_COUNTS:
                if learner_state.get(name) is None:
                    continue
                number, reason = _count(learner_state, name)
                if reason:
                    return WorkspaceValidation(reason=reason)
                values[name] = number

        answer, answer_invalid = parse_answer(learner_state.get("answer"))
        workspace = Workspace(
            interaction=interaction,
            values=MappingProxyType(values),
            answer=answer,
            answer_invalid=answer_invalid,
        )
        return WorkspaceValidation(workspace=workspace,
                                   warnings=conservation_warnings(question, values))
    except Exception as exc:  # defensive: layer 2 must never raise
        return WorkspaceValidation(reason=f"workspace_check_error:{type(exc).__name__}")
