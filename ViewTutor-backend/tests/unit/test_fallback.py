"""Fallbacks: every fixed text passes the same checks as LLM text (acceptance test 1)."""
from __future__ import annotations

import pytest

from app.answer_protection import check_response, number_values
from app.evaluator import evaluate
from app.fallback import NEUTRAL_MESSAGE, SAFE_MESSAGE, choose_fallback, confirmation
from app.questions import QUESTIONS
from app.schemas import SUPPORT_TYPES, TutorRequest
from app.strategies import strategy_context
from app.validation import validate_workspace


def states(q):
    p, i = q["parameters"], q["interaction"]
    if i == "JOIN":
        return [{"added_count": 0, "current_count": 0},
                {"added_count": 0, "current_count": p["initial"]},
                {"added_count": p["change"], "current_count": p["result"]},
                {"added_count": p["change"] + 1, "current_count": p["result"] + 1},
                {"added_count": -1, "current_count": p["initial"] - 1},
                {"added_count": 0, "current_count": 1, "part_a_count": 0, "part_b_count": 1},
                {"added_count": 0, "current_count": p["change"] + 1, "part_a_count": 0,
                 "part_b_count": p["change"] + 1}]
    if i == "REMOVE":
        return [{"removed_count": 0, "remaining_count": p["initial"]},
                {"removed_count": p["change"], "remaining_count": p["result"]},
                {"removed_count": p["change"] + 1, "remaining_count": p["result"] - 1}]
    if i == "EQUAL_GROUPS":
        return [{"group_sizes": [], "undistributed_count": p["total"]},
                {"group_sizes": [p["group_size"]] * p["group_count"], "undistributed_count": 0},
                {"group_sizes": [p["group_size"] + 1], "undistributed_count": 0},
                {"group_sizes": [p["group_size"]] * (p["group_count"] - 1), "undistributed_count": p["group_size"]}]
    if i == "EQUAL_SHARING":
        n = p["recipient_count"]
        return [{"share_sizes": [0] * n, "undistributed_count": p["total"]},
                {"share_sizes": [p["share_size"]] * n, "undistributed_count": 0},
                {"share_sizes": [p["share_size"] + 1] + [0] * (n - 1), "undistributed_count": 0},
                {"share_sizes": [1] + [0] * (n - 1), "undistributed_count": p["total"] - 1}]
    return [{"part_a_count": 0, "part_b_count": 0, "unassigned_a": p["part_a"], "unassigned_b": p["part_b"]},
            {"part_a_count": p["part_a"], "part_b_count": p["part_b"], "unassigned_a": 0, "unassigned_b": 0},
            {"part_a_count": p["part_a"] + 1, "part_b_count": 0, "unassigned_a": 0, "unassigned_b": 0}]


def setup(q, state, support_type, message="", history=None):
    request = TutorRequest(question_id=q["id"], learner_state=state, support_type=support_type,
                           student_message=message, conversation_history=history or [])
    evaluation = evaluate(q, validate_workspace(q, state).workspace)
    facts = dict(evaluation.facts)
    return request, facts, strategy_context(q, facts, support_type)


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_every_fallback_passes_checks_or_is_the_safe_message(question):
    for state in states(question):
        for support_type in SUPPORT_TYPES:
            for message in ("", "I don't get it"):
                request, facts, context = setup(question, state, support_type, message)
                fallback = choose_fallback(question, request, facts, context)
                if fallback.source == "safe_message":
                    assert fallback.passed_checks is False
                    assert fallback.text == SAFE_MESSAGE
                else:
                    assert fallback.passed_checks
                    assert check_response(fallback.text, question, request, facts, context,
                                          check_repetition=False) is None, (support_type, state)


def test_safe_message_is_rare():
    used = total = 0
    for question in QUESTIONS:
        for state in states(question):
            for support_type in SUPPORT_TYPES:
                request, facts, context = setup(question, state, support_type)
                total += 1
                used += choose_fallback(question, request, facts, context).source == "safe_message"
    assert used / total < 0.01, (used, total)


def test_fixed_messages_contain_no_numbers():
    assert number_values(SAFE_MESSAGE) == set()
    assert number_values(NEUTRAL_MESSAGE) == set()


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_confirmation_for_correct_work_has_no_numbers(question):
    correct = states(question)[2 if question["interaction"] == "JOIN" else 1]
    for support_type in SUPPORT_TYPES:
        request, facts, context = setup(question, correct, support_type)
        assert facts["student_correct"] is True
        result = confirmation(question, request, facts, context)
        assert result.passed_checks and number_values(result.text) == set()


def test_repetition_moves_to_another_variant():
    question = QUESTIONS[0]
    state = states(question)[1]
    request, facts, context = setup(question, state, "HINT")
    first = choose_fallback(question, request, facts, context).text
    request2, facts2, context2 = setup(question, state, "HINT", history=[{"role": "tutor", "content": first}])
    second = choose_fallback(question, request2, facts2, context2)
    assert second.text != first and second.passed_checks


# --- Fallback disclosure: a fallback never states the exact move -----------------

def test_no_fallback_states_an_exact_move():
    from app.fallback import states_exact_move
    from app.sample_states import sample_states

    checked = 0
    for question in QUESTIONS:
        for _, _, state in sample_states(question):
            for support_type in SUPPORT_TYPES:
                if support_type == "SMALLER_EXAMPLE":
                    continue
                request, facts, context = setup(question, state, support_type)
                fallback = choose_fallback(question, request, facts, context)
                assert not states_exact_move(fallback.text), (support_type, fallback.text)
                checked += 1
    assert checked > 3000


@pytest.mark.parametrize("text, is_move", [
    ("Move 2 more cookies into the removed area.", True),
    ("Create 4 more group areas.", True),
    ("Give the next cinnamon swirl to Jane, then keep the shares balanced.", True),
    ("Return 1 cookie to the starting collection.", True),
    ("Focus on the objects that leave. Look at the removed area and make a small change.", False),
    ("Compare the shares. Do all recipients currently have the same number?", False),
    ("Try making a group for the girls.", False),
])
def test_exact_move_detector(text, is_move):
    from app.fallback import states_exact_move

    assert states_exact_move(text) is is_move


def test_real_run1_fallbacks_are_no_longer_more_revealing():
    """The 10 real situations: the fallback must not state the move the model avoided."""
    import json

    from app.fallback import states_exact_move
    from app.questions import QUESTION_BY_ID
    from tests.conftest import FIXTURES

    cases = json.loads((FIXTURES / "real_run1_blocked.json").read_text(encoding="utf-8"))
    for case in cases:
        question = QUESTION_BY_ID[case["question_id"]]
        request, facts, context = setup(question, case["learner_state"], case["support_type"])
        fallback = choose_fallback(question, request, facts, context)
        assert fallback.passed_checks and not states_exact_move(fallback.text), fallback.text


def test_region_names_are_child_facing():
    from app.strategies import region_name

    sharing = next(q for q in QUESTIONS if q["visual"].get("recipient_labels"))
    assert region_name(sharing, "recipient", 0) == sharing["visual"]["recipient_labels"][0]
    groups = next(q for q in QUESTIONS if q["visual"].get("group_label") == "cousin")
    assert region_name(groups, "group", 1) == "Cousin 2"
