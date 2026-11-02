"""Evaluator: three statuses with priority incorrect > correct > incomplete; answer checked separately."""
from __future__ import annotations

import pytest

from app.evaluator import evaluate, hidden_answer
from app.questions import QUESTION_BY_ID, QUESTIONS
from app.validation import validate_workspace


def q(interaction: str, unknown: str | None = None) -> dict:
    return next(x for x in QUESTIONS if x["interaction"] == interaction
                and (unknown is None or x["unknown_position"] == unknown))


def run(question: dict, state: dict):
    result = validate_workspace(question, state)
    assert result.ok, result.reason
    return evaluate(question, result.workspace)


# --- Parity with v4 on real Unity requests ------------------------------------

def test_student_correct_matches_v4_on_all_logged_requests(logged_requests):
    for logged in logged_requests:
        question = QUESTION_BY_ID[logged["question_id"]]
        evaluation = run(question, logged["learner_state"])
        assert evaluation.student_correct == logged["v4_student_correct"], logged
        assert evaluation.conversation_status == logged["v4_conversation_status"], logged


# --- JOIN -----------------------------------------------------------------------

JOIN = QUESTION_BY_ID["MC-JOIN-nluds-0001"]  # 7 red + 2 green = 9


@pytest.mark.parametrize("state, status", [
    ({"added_count": 2, "current_count": 9}, "correct"),
    ({"added_count": 1, "current_count": 8}, "incomplete"),
    ({"added_count": 3, "current_count": 10}, "incorrect"),       # too many
    ({"added_count": -4, "current_count": 3}, "incomplete"),      # starting objects moved out: putting them back fixes it
    ({"added_count": 0, "current_count": 7}, "incomplete"),
])
def test_join_totals_mode(state, status):
    assert run(JOIN, state).construction_status == status


@pytest.mark.parametrize("a, b, status", [
    (7, 2, "correct"),
    (7, 1, "incomplete"),
    (3, 0, "incomplete"),
    (0, 7, "incorrect"),      # 7 green, story has 2: definite error even though unfinished
    (8, 0, "incorrect"),
    (6, 3, "incorrect"),      # right total (9), wrong split
])
def test_join_two_part_mode(a, b, status):
    state = {"added_count": max(0, a + b - 7), "current_count": a + b,
             "part_a_count": a, "part_b_count": b, "total_count": a + b,
             "workspace_mode": "single_destination_two_sources"}
    assert run(JOIN, state).construction_status == status


def test_join_wrong_split_is_not_correct_unlike_v4():
    # v4 judged only added_count / current_count: 6 red + 3 green gives added 2, current 9
    # and v4 would call it correct. The part counts show it is wrong.
    state = {"added_count": 2, "current_count": 9, "part_a_count": 6, "part_b_count": 3}
    evaluation = run(JOIN, state)
    assert evaluation.construction_status == "incorrect"
    assert evaluation.student_correct is False


# --- REMOVE ---------------------------------------------------------------------

def test_remove_statuses():
    question = q("REMOVE", "RESULT")
    p = question["parameters"]
    change, result = p["change"], p["result"]
    assert run(question, {"removed_count": change, "remaining_count": result}).construction_status == "correct"
    assert run(question, {"removed_count": 0, "remaining_count": p["initial"]}).construction_status == "incomplete"
    assert run(question, {"removed_count": change + 1, "remaining_count": result - 1}).construction_status == "incorrect"


# --- EQUAL_GROUPS ----------------------------------------------------------------

def test_equal_groups_statuses():
    question = q("EQUAL_GROUPS")
    p = question["parameters"]
    count, size = p["group_count"], p["group_size"]
    full = [size] * count
    assert run(question, {"group_sizes": full, "undistributed_count": 0}).construction_status == "correct"
    assert run(question, {"group_sizes": [], "undistributed_count": p["total"]}).construction_status == "incomplete"
    assert run(question, {"group_sizes": full[:-1], "undistributed_count": size}).construction_status == "incomplete"
    # Unfinished but one group already too big → incorrect, not incomplete.
    assert run(question, {"group_sizes": [size + 1], "undistributed_count": 0}).construction_status == "incorrect"
    assert run(question, {"group_sizes": full + [0], "undistributed_count": 0}).construction_status == "incorrect"
    # Right groups but objects left in the bank → incomplete.
    assert run(question, {"group_sizes": full, "undistributed_count": 1}).construction_status == "incomplete"


# --- EQUAL_SHARING ---------------------------------------------------------------

def test_equal_sharing_statuses():
    question = q("EQUAL_SHARING")
    p = question["parameters"]
    n, share = p["recipient_count"], p["share_size"]
    assert run(question, {"share_sizes": [share] * n, "undistributed_count": 0}).construction_status == "correct"
    # Uneven while dealing out is unfinished, not wrong.
    uneven = [1] + [0] * (n - 1)
    assert run(question, {"share_sizes": uneven, "undistributed_count": p["total"] - 1}).construction_status == "incomplete"
    over = [share + 1] + [0] * (n - 1)
    assert run(question, {"share_sizes": over, "undistributed_count": 0}).construction_status == "incorrect"


# --- RATIO -----------------------------------------------------------------------

def test_ratio_statuses():
    question = q("PART_TO_PART_RATIO")
    a, b = question["parameters"]["part_a"], question["parameters"]["part_b"]
    base = {"unassigned_a": 0, "unassigned_b": 0}
    assert run(question, {**base, "part_a_count": a, "part_b_count": b}).construction_status == "correct"
    assert run(question, {**base, "part_a_count": a, "part_b_count": 0}).construction_status == "incomplete"
    assert run(question, {**base, "part_a_count": a + 1, "part_b_count": 0}).construction_status == "incorrect"
    assert run(question, {"part_a_count": a, "part_b_count": b, "unassigned_a": 1,
                          "unassigned_b": 0}).construction_status == "incomplete"


# --- Entered answer, separately from the construction ----------------------------

CORRECT_JOIN = {"added_count": 2, "current_count": 9}


@pytest.mark.parametrize("answer, entered, parseable, correct, student_correct", [
    (None, False, False, None, True),
    ("", False, False, None, True),
    (9, True, True, True, True),
    ("9", True, True, True, True),
    (9.0, True, True, True, True),
    (8, True, True, False, False),       # correct build, wrong answer → not correct
    (9.5, True, False, False, False),
    ("unknown", True, False, False, False),
    (True, True, False, False, False),
])
def test_answer_checked_separately(answer, entered, parseable, correct, student_correct):
    evaluation = run(JOIN, {**CORRECT_JOIN, "answer": answer})
    assert evaluation.construction_status == "correct"
    assert (evaluation.answer_entered, evaluation.answer_parseable, evaluation.answer_correct) == (
        entered, parseable, correct)
    assert evaluation.student_correct is student_correct
    assert evaluation.conversation_status == ("correct" if student_correct else "continue")


def test_right_answer_with_wrong_construction_is_not_correct():
    evaluation = run(JOIN, {"added_count": 1, "current_count": 8, "answer": 9})
    assert evaluation.answer_correct is True
    assert evaluation.student_correct is False


def test_ratio_answer_is_not_numeric():
    question = q("PART_TO_PART_RATIO")
    a, b = question["parameters"]["part_a"], question["parameters"]["part_b"]
    state = {"part_a_count": a, "part_b_count": b, "unassigned_a": 0, "unassigned_b": 0, "answer": 42}
    assert run(question, state).student_correct is True
    assert run(question, {**state, "answer": "abc"}).student_correct is False


# --- Error messages never state a hidden target ------------------------------------

def _error_states(question: dict) -> list[dict]:
    """Several wrong states per question, each producing at least one error."""
    p = question["parameters"]
    i = question["interaction"]
    if i == "JOIN":
        return [{"added_count": p["change"] + 1, "current_count": p["result"] + 1},
                {"added_count": -1, "current_count": p["initial"] - 1},
                {"added_count": 0, "current_count": p["initial"] + p["change"] + 1,
                 "part_a_count": p["initial"], "part_b_count": p["change"] + 1}]
    if i == "REMOVE":
        return [{"removed_count": p["change"] + 1, "remaining_count": max(p["result"] - 1, 0)}]
    if i == "EQUAL_GROUPS":
        return [{"group_sizes": [p["group_size"] + 1] * (p["group_count"] + 1), "undistributed_count": 0}]
    if i == "EQUAL_SHARING":
        return [{"share_sizes": [p["share_size"] + 1] * (p["recipient_count"] + 1), "undistributed_count": 0}]
    return [{"part_a_count": p["part_a"] + 1, "part_b_count": p["part_b"] + 1,
             "unassigned_a": 0, "unassigned_b": 0}]


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda x: x["id"])
def test_error_messages_hide_the_answer(question):
    import re

    from app.questions import student_safe

    answer = hidden_answer(question)
    # Quantities the story states openly are quotable even when equal to the answer (v4 rule).
    stated = {v for v in student_safe(question)["parameters"].values() if isinstance(v, int)}
    for state in _error_states(question):
        evaluation = run(question, state)
        assert evaluation.errors or evaluation.notes, state
        visible = {abs(v) for v in state.values() if isinstance(v, int)}
        visible |= {n for v in state.values() if isinstance(v, list) for n in v}
        visible |= {len(v) for v in state.values() if isinstance(v, list)}
        positions = {n for v in state.values() if isinstance(v, list) for n in range(1, len(v) + 1)}
        for message in evaluation.errors + evaluation.notes:
            numbers = {int(n) for n in re.findall(r"\d+", message)}
            if answer in numbers:
                # Allowed only as a visible count, a stated quantity, or a position label.
                assert answer in visible | stated | positions, (message, answer)
            # The hidden target itself is never named as a target.
            assert "story ends with" not in message or answer not in numbers - visible


# --- Hidden answer ----------------------------------------------------------------

def test_hidden_answer_per_type():
    assert hidden_answer(JOIN) == 9
    change_q = q("JOIN", "CHANGE")
    assert hidden_answer(change_q) == change_q["parameters"]["change"]
    assert hidden_answer(q("EQUAL_GROUPS")) == q("EQUAL_GROUPS")["parameters"]["total"]
    assert hidden_answer(q("EQUAL_SHARING")) == q("EQUAL_SHARING")["parameters"]["share_size"]
    assert hidden_answer(q("PART_TO_PART_RATIO")) == -1


def test_every_question_has_a_reachable_correct_state():
    """Each of the 88 questions can be marked correct by the evaluator."""
    for question in QUESTIONS:
        p = question["parameters"]
        state = {
            "JOIN": {"added_count": p.get("change"), "current_count": p.get("result")},
            "REMOVE": {"removed_count": p.get("change"), "remaining_count": p.get("result")},
            "EQUAL_GROUPS": {"group_sizes": [p.get("group_size")] * (p.get("group_count") or 0),
                             "undistributed_count": 0},
            "EQUAL_SHARING": {"share_sizes": [p.get("share_size")] * (p.get("recipient_count") or 0),
                              "undistributed_count": 0},
            "PART_TO_PART_RATIO": {"part_a_count": p.get("part_a"), "part_b_count": p.get("part_b"),
                                   "unassigned_a": 0, "unassigned_b": 0},
        }[question["interaction"]]
        assert run(question, state).student_correct, question["id"]


def test_starting_objects_moved_out_is_a_note_not_an_error():
    evaluation = run(JOIN, {"added_count": -2, "current_count": 5})
    assert evaluation.construction_status == "incomplete"
    assert evaluation.errors == () and "moved out" in evaluation.notes[0]


def test_independent_math_check_agrees():
    """scripts/check_math.py: add-only simulation, shares no logic with the evaluator."""
    from scripts.check_math import check

    result = check(quick=True)
    assert sum(result["checked"].values()) > 10000
    assert result["disagreements"] == []
    assert result["answer_errors"] == []
