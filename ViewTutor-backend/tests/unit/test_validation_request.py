"""Layer 1: request validation. Never raises; tutoring is never blocked by text."""
from __future__ import annotations

import copy

import pytest

from app.questions import QUESTION_BY_ID
from app.validation import (
    MAX_HISTORY_TURNS,
    MAX_LATEST_ACTION,
    validate_request,
    validate_workspace,
)

QID = "MC-JOIN-nluds-0001"


def base_request(**overrides):
    request = {
        "question_id": QID,
        "learner_state": {"added_count": 2, "current_count": 9, "answer": None},
        "support_type": "HINT",
        "latest_action": "",
        "student_message": "",
        "conversation_history": [],
    }
    request.update(overrides)
    return request


# --- Real Unity requests ------------------------------------------------------

def test_all_logged_unity_requests_pass_both_layers(logged_requests):
    assert len(logged_requests) == 145
    for logged in logged_requests:
        raw = {k: logged[k] for k in ("question_id", "support_type", "learner_state", "latest_action", "student_message")}
        result = validate_request(raw, QUESTION_BY_ID)
        assert result.ok, (logged["question_id"], result.reason)
        workspace = validate_workspace(result.question, result.request.learner_state)
        assert workspace.ok, (logged["question_id"], workspace.reason)


def test_logged_requests_cover_all_interactions(logged_requests):
    interactions = {QUESTION_BY_ID[r["question_id"]]["interaction"] for r in logged_requests}
    assert interactions == {"JOIN", "REMOVE", "EQUAL_GROUPS", "EQUAL_SHARING", "PART_TO_PART_RATIO"}


@pytest.mark.parametrize("support_type", [
    "AUTO_CHECK", "SIMPLIFY_STORY", "INTERFACE_HELP", "CHECK_WORK",
    "SMALLER_EXAMPLE", "UNSURE", "HINT", "OPEN_ENDED",
])
def test_all_eight_support_types_accepted_as_strings(support_type):
    result = validate_request(base_request(support_type=support_type), QUESTION_BY_ID)
    assert result.ok and result.request.support_type == support_type


def test_support_type_is_case_sensitive():
    # Unity sends the exact upper-case names; anything else is rejected, not guessed.
    assert validate_request(base_request(support_type="hint"), QUESTION_BY_ID).reason == "support_type_unknown"


# --- Optional view block ------------------------------------------------------

def test_request_without_view_field():
    result = validate_request(base_request(), QUESTION_BY_ID)
    assert result.ok and result.request.view is None and result.warnings == []


def test_request_with_view_null():
    result = validate_request(base_request(view=None), QUESTION_BY_ID)
    assert result.ok and result.request.view is None


def test_request_with_full_view_is_kept():
    view = {
        "gaze_target": "desk",
        "head_position": [0.0, 1.2, 0.0],
        "head_forward": [0.0, -0.3, 0.95],
        "fov_deg": [104.0, 96.0],
        "regions": [{"region_id": "friend_1", "visible_fraction": 0.8, "label_visible": True,
                     "label_seen_this_attempt": True}],
        "last_touched_region_id": "friend_1",
        "attempt_id": "a1",
    }
    result = validate_request(base_request(view=view), QUESTION_BY_ID)
    assert result.ok
    assert result.request.view.regions[0].visible_fraction == 0.8


def test_request_with_all_view_fields_null():
    view = {"gaze_target": None, "regions": [{"region_id": None, "visible_fraction": None}]}
    assert validate_request(base_request(view=view), QUESTION_BY_ID).ok


def test_invalid_view_is_dropped_not_rejected():
    result = validate_request(base_request(view={"regions": [{"visible_fraction": 7}]}), QUESTION_BY_ID)
    assert result.ok
    assert result.request.view is None
    assert "view_invalid_dropped" in result.warnings


# --- Normalization instead of rejection ---------------------------------------

def test_unknown_fields_are_ignored():
    assert validate_request(base_request(something_new=123), QUESTION_BY_ID).ok


def test_null_text_fields_become_empty():
    result = validate_request(base_request(latest_action=None, student_message=None,
                                           conversation_history=None), QUESTION_BY_ID)
    assert result.ok
    assert result.request.latest_action == "" and result.request.student_message == ""


def test_long_latest_action_is_truncated_not_rejected():
    result = validate_request(base_request(latest_action="x" * 5000), QUESTION_BY_ID)
    assert result.ok
    assert len(result.request.latest_action) == MAX_LATEST_ACTION
    assert "latest_action_truncated" in result.warnings


def test_long_student_message_is_truncated_not_rejected():
    from app.validation import MAX_STUDENT_MESSAGE

    result = validate_request(base_request(student_message="y" * 2000), QUESTION_BY_ID)
    assert result.ok
    assert len(result.request.student_message) == MAX_STUDENT_MESSAGE
    assert "student_message_truncated" in result.warnings


def test_learner_state_is_never_modified():
    state = {"added_count": "2", "current_count": 9.0, "answer": "x", "extra": [1, 2]}
    before = copy.deepcopy(state)
    result = validate_request(base_request(learner_state=state), QUESTION_BY_ID)
    validate_workspace(result.question, result.request.learner_state)
    assert state == before
    assert result.request.learner_state == before


def test_bad_history_turns_are_dropped():
    history = [
        {"role": "student", "content": "hi"},
        {"role": "assistant", "content": "unknown role"},
        {"role": "tutor", "content": "   "},
        "not an object",
        {"role": "tutor", "content": "ok"},
    ]
    result = validate_request(base_request(conversation_history=history), QUESTION_BY_ID)
    assert result.ok
    assert [m.content for m in result.request.conversation_history] == ["hi", "ok"]
    assert "conversation_history_turn_dropped" in result.warnings


def test_history_is_capped_to_recent_turns():
    history = [{"role": "student", "content": f"m{i}"} for i in range(MAX_HISTORY_TURNS + 10)]
    result = validate_request(base_request(conversation_history=history), QUESTION_BY_ID)
    assert len(result.request.conversation_history) == MAX_HISTORY_TURNS
    assert result.request.conversation_history[-1].content == f"m{MAX_HISTORY_TURNS + 9}"


def test_missing_support_type_defaults_to_auto_check():
    raw = base_request()
    del raw["support_type"]
    result = validate_request(raw, QUESTION_BY_ID)
    assert result.ok and result.request.support_type == "AUTO_CHECK"


def test_request_id_is_kept_when_string():
    result = validate_request(base_request(request_id="r-1"), QUESTION_BY_ID)
    assert result.request.request_id == "r-1"


# --- Rejections ---------------------------------------------------------------

@pytest.mark.parametrize("raw, reason", [
    ("not a dict", "body_not_object"),
    (None, "body_not_object"),
    ({}, "question_id_missing"),
    ({"question_id": ""}, "question_id_missing"),
    ({"question_id": 5}, "question_id_missing"),
    ({"question_id": "NOPE"}, "question_id_unknown"),
    ({"question_id": QID, "learner_state": "x"}, "learner_state_not_object"),
    ({"question_id": QID, "learner_state": None}, "learner_state_not_object"),
    ({"question_id": QID, "learner_state": {}, "support_type": "MAGIC"}, "support_type_unknown"),
    ({"question_id": QID, "learner_state": {}, "support_type": 3}, "support_type_unknown"),
])
def test_rejections_have_reasons(raw, reason):
    result = validate_request(raw, QUESTION_BY_ID)
    assert not result.ok
    assert result.reason == reason


@pytest.mark.parametrize("raw", [
    [], 0, 3.5, True, {"question_id": ["x"]}, {"question_id": {"a": 1}},
    {"question_id": QID, "learner_state": {}, "support_type": ["HINT"]},
    {"question_id": QID, "learner_state": {}, "conversation_history": {"a": 1}},
    {"question_id": QID, "learner_state": {}, "view": "garbage"},
])
def test_never_raises(raw):
    result = validate_request(copy.deepcopy(raw), QUESTION_BY_ID)
    assert result.ok or result.reason
