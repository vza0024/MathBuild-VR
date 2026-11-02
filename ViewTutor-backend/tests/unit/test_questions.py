"""Question store: the v4 data and filter, unchanged."""
from __future__ import annotations

import hashlib
import json
from collections import Counter

import pytest

from app.config import QUESTIONS_FILE
from app.questions import (
    INTERACTIONS,
    QUESTIONS,
    STUDENT_QUESTIONS,
    QuestionDataError,
    load_questions,
)
from tests.conftest import FIXTURES

V4_QUESTIONS_SHA256 = "adaf65995a5e585c929a3304ab387e4ebaff0c0136d4c86cef1db13e01d3953f"


def test_question_file_is_v4_unchanged():
    assert hashlib.sha256(QUESTIONS_FILE.read_bytes()).hexdigest() == V4_QUESTIONS_SHA256


def test_counts_per_interaction():
    counts = Counter(q["interaction"] for q in QUESTIONS)
    assert counts == {
        "JOIN": 20,
        "REMOVE": 20,
        "EQUAL_GROUPS": 20,
        "EQUAL_SHARING": 20,
        "PART_TO_PART_RATIO": 8,
    }


def test_every_interaction_has_questions():
    present = {q["interaction"] for q in STUDENT_QUESTIONS}
    assert present == set(INTERACTIONS)


def test_student_copy_is_identical_to_v4_output():
    v4 = json.loads((FIXTURES / "v4_student_questions.json").read_text(encoding="utf-8"))
    assert STUDENT_QUESTIONS == v4


def test_student_copy_hides_answer_and_formula():
    for question in STUDENT_QUESTIONS:
        assert "answer" not in question
        assert "formula" not in question


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_hidden_quantity_not_sent(question):
    safe = next(q for q in STUDENT_QUESTIONS if q["id"] == question["id"])
    params = safe["parameters"]
    interaction = question["interaction"]
    hidden = {
        "EQUAL_GROUPS": "total",
        "EQUAL_SHARING": "share_size",
    }.get(interaction)
    if interaction in {"JOIN", "REMOVE"}:
        hidden = "change" if question["unknown_position"] == "CHANGE" else "result"
    if hidden:
        assert hidden not in params


def _write(tmp_path, questions):
    path = tmp_path / "q.json"
    path.write_text(json.dumps(questions), encoding="utf-8")
    return path


def test_rejects_inconsistent_arithmetic(tmp_path):
    bad = [dict(q) for q in QUESTIONS]
    join = next(i for i, q in enumerate(bad) if q["interaction"] == "JOIN")
    bad[join] = {**bad[join], "parameters": {**bad[join]["parameters"], "result": 999}}
    with pytest.raises(QuestionDataError, match="initial \\+ change"):
        load_questions(_write(tmp_path, bad))


def test_rejects_duplicate_ids(tmp_path):
    with pytest.raises(QuestionDataError, match="duplicate"):
        load_questions(_write(tmp_path, QUESTIONS + [QUESTIONS[0]]))


def test_rejects_missing_interaction_type(tmp_path):
    without_ratio = [q for q in QUESTIONS if q["interaction"] != "PART_TO_PART_RATIO"]
    with pytest.raises(QuestionDataError, match="PART_TO_PART_RATIO"):
        load_questions(_write(tmp_path, without_ratio))


def test_rejects_empty_file(tmp_path):
    with pytest.raises(QuestionDataError):
        load_questions(_write(tmp_path, []))
