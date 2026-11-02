"""Layer 2: learner-state validation per interaction type. Never raises."""
from __future__ import annotations

import pytest

from app.questions import QUESTIONS
from app.validation import MAX_COUNT, parse_answer, parse_whole_number, validate_workspace


def question_for(interaction: str) -> dict:
    return next(q for q in QUESTIONS if q["interaction"] == interaction)


VALID = {
    "JOIN": {"added_count": 2, "current_count": 9, "answer": None},
    "REMOVE": {"removed_count": 1, "remaining_count": 4, "answer": None},
    "EQUAL_GROUPS": {"group_sizes": [2, 2, 1], "undistributed_count": 1, "answer": None},
    "EQUAL_SHARING": {"share_sizes": [5, 4, 3], "undistributed_count": 0, "answer": None},
    "PART_TO_PART_RATIO": {"part_a_count": 2, "part_b_count": 3, "unassigned_a": 0, "unassigned_b": 1,
                           "answer": None},
}
REQUIRED = {
    "JOIN": ["added_count", "current_count"],
    "REMOVE": ["removed_count", "remaining_count"],
    "EQUAL_GROUPS": ["group_sizes", "undistributed_count"],
    "EQUAL_SHARING": ["share_sizes", "undistributed_count"],
    "PART_TO_PART_RATIO": ["part_a_count", "part_b_count", "unassigned_a", "unassigned_b"],
}


@pytest.mark.parametrize("interaction", VALID)
def test_valid_state_passes(interaction):
    result = validate_workspace(question_for(interaction), VALID[interaction])
    assert result.ok, result.reason
    assert result.workspace.interaction == interaction
    assert result.workspace.answer is None and result.workspace.answer_invalid is False


@pytest.mark.parametrize("interaction, name", [(i, n) for i, names in REQUIRED.items() for n in names])
def test_missing_required_field_is_rejected(interaction, name):
    state = dict(VALID[interaction])
    del state[name]
    result = validate_workspace(question_for(interaction), state)
    assert not result.ok and result.reason == f"{name}_missing"


@pytest.mark.parametrize("interaction, name", [(i, n) for i, names in REQUIRED.items() for n in names])
def test_null_required_field_is_rejected(interaction, name):
    state = {**VALID[interaction], name: None}
    assert not validate_workspace(question_for(interaction), state).ok


@pytest.mark.parametrize("bad, reason_suffix", [
    (-1, "negative"),
    (2.5, "not_whole_number"),
    (True, "not_whole_number"),
    ("abc", "not_whole_number"),
    (MAX_COUNT + 1, "too_large"),
])
def test_bad_count_values(bad, reason_suffix):
    result = validate_workspace(question_for("REMOVE"), {**VALID["REMOVE"], "removed_count": bad})
    assert result.reason == f"removed_count_{reason_suffix}"


def test_join_added_count_may_be_negative():
    # Real Unity state: 7 apples at the start, child moved 4 out → added_count = -4.
    result = validate_workspace(question_for("JOIN"), {"added_count": -4, "current_count": 3, "answer": None})
    assert result.ok and result.workspace.values["added_count"] == -4


def test_join_current_count_may_not_be_negative():
    result = validate_workspace(question_for("JOIN"), {"added_count": 0, "current_count": -1, "answer": None})
    assert result.reason == "current_count_negative"


def test_signed_field_still_has_a_size_limit():
    result = validate_workspace(question_for("JOIN"), {"added_count": -(MAX_COUNT + 1), "current_count": 0})
    assert result.reason == "added_count_too_large"


def test_v4_parity_numeric_text_and_whole_floats_are_accepted():
    result = validate_workspace(question_for("REMOVE"),
                                {"removed_count": "3", "remaining_count": 4.0, "answer": None})
    assert result.ok
    assert dict(result.workspace.values) == {"removed_count": 3, "remaining_count": 4}


@pytest.mark.parametrize("bad, reason", [
    ("3,2", "group_sizes_not_list"),
    ({"a": 1}, "group_sizes_not_list"),
    ([2, "x"], "group_sizes_not_whole_numbers"),
    ([2, -1], "group_sizes_negative"),
    ([2, True], "group_sizes_not_whole_numbers"),
    ([1] * 51, "group_sizes_too_long"),
])
def test_bad_lists(bad, reason):
    result = validate_workspace(question_for("EQUAL_GROUPS"), {**VALID["EQUAL_GROUPS"], "group_sizes": bad})
    assert result.reason == reason


def test_empty_list_is_allowed():
    # A learner may not have built any groups yet.
    result = validate_workspace(question_for("EQUAL_GROUPS"), {**VALID["EQUAL_GROUPS"], "group_sizes": []})
    assert result.ok and result.workspace.values["group_sizes"] == ()


def test_join_optional_fields_parsed_when_present():
    state = {**VALID["JOIN"], "part_a_count": 7, "part_b_count": 2, "total_count": 9,
             "workspace_mode": "two_destinations", "part_b_count_extra": "ignored"}
    result = validate_workspace(question_for("JOIN"), state)
    assert result.ok
    assert result.workspace.values["total_count"] == 9


def test_join_optional_null_is_skipped():
    state = {**VALID["JOIN"], "part_a_count": None, "part_b_count": None}
    result = validate_workspace(question_for("JOIN"), state)
    assert result.ok and "part_a_count" not in result.workspace.values


def test_join_optional_negative_is_rejected():
    state = {**VALID["JOIN"], "total_count": -2}
    assert validate_workspace(question_for("JOIN"), state).reason == "total_count_negative"


@pytest.mark.parametrize("value, expected", [
    (None, (None, False)),
    ("", (None, False)),
    (7, (7, False)),
    ("7", (7, False)),
    (7.0, (7, False)),
    (7.5, (None, True)),
    ("seven", (None, True)),
    (True, (None, True)),
])
def test_answer_parsing_matches_v4(value, expected):
    assert parse_answer(value) == expected


def test_invalid_answer_does_not_reject_the_state():
    result = validate_workspace(question_for("JOIN"), {**VALID["JOIN"], "answer": "seven"})
    assert result.ok and result.workspace.answer_invalid is True


def test_whole_number_parser():
    assert parse_whole_number(False) is None
    assert parse_whole_number(" 12 ") == 12
    assert parse_whole_number(float("nan")) is None


@pytest.mark.parametrize("question", [{}, {"interaction": "UNKNOWN"}, {"interaction": None}])
def test_never_raises_on_bad_question(question):
    result = validate_workspace(question, VALID["JOIN"])
    assert not result.ok and result.reason.startswith("workspace_check_error")


def test_workspace_values_are_read_only():
    result = validate_workspace(question_for("JOIN"), VALID["JOIN"])
    with pytest.raises(TypeError):
        result.workspace.values["added_count"] = 99  # type: ignore[index]
