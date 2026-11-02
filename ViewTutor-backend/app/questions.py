"""Question store: the 88 curated ASDiv problems from v4, unchanged.

Ported from v4 `question_store.py`. The student-safe filter is identical: the
answer and formula are removed, and only the quantities the interface needs to
render the problem are sent to Unity.

On load, every question is checked for internal consistency (the stated
quantities must agree with the arithmetic). A broken file stops the server at
startup instead of producing wrong tutoring at runtime.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.config import QUESTIONS_FILE

INTERACTIONS: tuple[str, ...] = (
    "JOIN",
    "REMOVE",
    "EQUAL_GROUPS",
    "EQUAL_SHARING",
    "PART_TO_PART_RATIO",
)

# Parameters each interaction needs (v4 `question_store._VISIBLE_PARAMETERS`).
_VISIBLE_PARAMETERS: dict[str, tuple[str, ...]] = {
    "JOIN": ("initial", "change"),
    "REMOVE": ("initial", "change"),
    "EQUAL_GROUPS": ("group_count", "group_size"),
    "EQUAL_SHARING": ("total", "recipient_count"),
    "PART_TO_PART_RATIO": ("part_a", "part_b"),
}
_HIDDEN_FIELDS: tuple[str, ...] = ("answer", "formula")


class QuestionDataError(ValueError):
    """The question file is malformed or internally inconsistent."""


def _check_question(question: dict[str, Any]) -> None:
    """Raise QuestionDataError if a question's quantities do not agree."""
    qid = question.get("id", "<missing id>")
    interaction = question.get("interaction")
    if interaction not in INTERACTIONS:
        raise QuestionDataError(f"{qid}: unknown interaction {interaction!r}")
    params = question.get("parameters") or {}

    def need(*names: str) -> list[int]:
        values = []
        for name in names:
            value = params.get(name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise QuestionDataError(f"{qid}: parameter {name!r} must be a whole number >= 0")
            values.append(value)
        return values

    if interaction == "JOIN":
        initial, change, result = need("initial", "change", "result")
        if initial + change != result:
            raise QuestionDataError(f"{qid}: initial + change != result")
    elif interaction == "REMOVE":
        initial, change, result = need("initial", "change", "result")
        if initial - change != result:
            raise QuestionDataError(f"{qid}: initial - change != result")
    elif interaction == "EQUAL_GROUPS":
        count, size, total = need("group_count", "group_size", "total")
        if count * size != total:
            raise QuestionDataError(f"{qid}: group_count * group_size != total")
    elif interaction == "EQUAL_SHARING":
        total, recipients, share = need("total", "recipient_count", "share_size")
        if recipients == 0 or recipients * share != total:
            raise QuestionDataError(f"{qid}: recipient_count * share_size != total")
    else:
        need("part_a", "part_b")


def load_questions(path: Path = QUESTIONS_FILE) -> list[dict[str, Any]]:
    """Load and check all questions. Raises QuestionDataError on any problem."""
    with path.open("r", encoding="utf-8") as handle:
        questions = json.load(handle)
    if not isinstance(questions, list) or not questions:
        raise QuestionDataError("question file must be a non-empty list")

    ids = Counter(q.get("id") for q in questions)
    duplicates = [qid for qid, n in ids.items() if n > 1]
    if duplicates:
        raise QuestionDataError(f"duplicate question ids: {duplicates}")

    for question in questions:
        _check_question(question)

    # Unity's startup fails if a type it needs has no questions.
    present = {q["interaction"] for q in questions}
    missing = [i for i in INTERACTIONS if i not in present]
    if missing:
        raise QuestionDataError(f"no questions for interaction types: {missing}")
    return questions


def student_safe(question: dict[str, Any]) -> dict[str, Any]:
    """Return the copy Unity receives: no answer, no formula, no hidden quantity.

    Identical to v4 `question_store._student_safe`.
    """
    interaction = question["interaction"]
    keep = list(_VISIBLE_PARAMETERS[interaction])
    if interaction in {"JOIN", "REMOVE"} and question.get("unknown_position") == "CHANGE":
        # The change is what the learner must find; the ending quantity is stated instead.
        keep = ["initial", "result"]
    safe = {key: value for key, value in question.items() if key not in _HIDDEN_FIELDS}
    safe["parameters"] = {
        key: value for key, value in question["parameters"].items() if key in keep
    }
    return safe


QUESTIONS: list[dict[str, Any]] = load_questions()
QUESTION_BY_ID: dict[str, dict[str, Any]] = {q["id"]: q for q in QUESTIONS}
STUDENT_QUESTIONS: list[dict[str, Any]] = [student_safe(q) for q in QUESTIONS]
