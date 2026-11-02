"""Scripted sample states are valid, physically consistent, and labelled correctly."""
from __future__ import annotations

from collections import Counter

import pytest

from app.evaluator import evaluate
from app.questions import QUESTIONS
from app.sample_states import sample_states
from app.validation import validate_workspace


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_states_validate_without_warnings_and_match_their_label(question):
    for label, expected, state in sample_states(question):
        check = validate_workspace(question, state)
        assert check.ok, (label, check.reason)
        assert check.warnings == [], (label, check.warnings)
        assert evaluate(question, check.workspace).construction_status == expected, label


def test_every_type_has_correct_incomplete_and_incorrect_states():
    seen = Counter()
    for question in QUESTIONS:
        for _, expected, _ in sample_states(question):
            seen[(question["interaction"], expected)] += 1
    for interaction in ("JOIN", "REMOVE", "EQUAL_GROUPS", "EQUAL_SHARING"):
        for status in ("correct", "incomplete", "incorrect"):
            assert seen[(interaction, status)] > 0, (interaction, status)
    # Ratio: Unity's fixed totals make an over-full part impossible, so no incorrect state.
    assert seen[("PART_TO_PART_RATIO", "correct")] and seen[("PART_TO_PART_RATIO", "incomplete")]


def test_join_states_follow_unity_added_count_rule():
    question = next(q for q in QUESTIONS if q["interaction"] == "JOIN")
    initial = question["parameters"]["initial"]
    for label, _, state in sample_states(question):
        if "part_a_count" in state:
            assert state["added_count"] == max(0, state["current_count"] - initial), label
        else:
            assert state["added_count"] == state["current_count"] - initial, label
