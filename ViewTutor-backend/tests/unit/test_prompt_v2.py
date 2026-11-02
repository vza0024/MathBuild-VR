"""Prompt v2 (default): plain arrangement description + two rules. v1 still selectable."""
from __future__ import annotations

import json
import re

import pytest

from app.config import Settings
from app.evaluator import evaluate, hidden_answer
from app.llm.prompts import PROMPT_VERSION, build_prompt, describe_arrangement
from app.questions import QUESTION_BY_ID, QUESTIONS, student_safe
from app.sample_states import sample_states
from app.schemas import TutorRequest
from app.strategies import strategy_context
from app.validation import validate_workspace


def make(question, state, version, support_type="HINT"):
    request = TutorRequest(question_id=question["id"], learner_state=state, support_type=support_type)
    evaluation = evaluate(question, validate_workspace(question, state).workspace)
    context = strategy_context(question, dict(evaluation.facts), support_type)
    return build_prompt(question, request, evaluation, context, version), evaluation


def test_default_is_v2_and_v1_still_works():
    assert PROMPT_VERSION == "step1-v2" and Settings().prompt_version == "step1-v2"
    question = QUESTIONS[0]
    prompt, _ = make(question, {"added_count": 0, "current_count": 7}, "step1-v1")
    assert "arrangement_description" not in json.loads(prompt.payload)
    assert "8. arrangement_description" not in prompt.instructions


def test_unknown_version_rejected():
    with pytest.raises(ValueError):
        make(QUESTIONS[0], {"added_count": 0, "current_count": 7}, "v9")


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_description_never_states_the_hidden_answer(question):
    answer = hidden_answer(question)
    stated = {v for v in student_safe(question)["parameters"].values() if isinstance(v, int)}
    for _, _, state in sample_states(question):
        prompt, _ = make(question, state, "step1-v2")
        lines = json.loads(prompt.payload)["arrangement_description"]
        visible = {abs(v) for v in state.values() if isinstance(v, int) and not isinstance(v, bool)}
        visible |= {n for v in state.values() if isinstance(v, list) for n in v}
        visible |= {len(v) for v in state.values() if isinstance(v, list)}
        positions = {n for v in state.values() if isinstance(v, list) for n in range(1, len(v) + 1)}
        for line in lines:
            numbers = {int(n) for n in re.findall(r"\d+", line)}
            if answer in numbers:
                assert answer in stated | visible | positions, (line, answer)


def test_join_misread_case_now_says_starting_apples_are_there():
    question = QUESTION_BY_ID["MC-JOIN-nluds-0001"]
    prompt, _ = make(question, {"added_count": 0, "current_count": 7}, "step1-v2")
    text = " ".join(json.loads(prompt.payload)["arrangement_description"])
    assert "All the starting apples are already in the collection" in text
    assert "9" not in re.findall(r"\d+", text)          # the answer (9) is not stated
    assert "Never tell the learner to place" in prompt.instructions


def test_ratio_misread_case_says_collections_exist():
    question = next(q for q in QUESTIONS if q["interaction"] == "PART_TO_PART_RATIO")
    p = question["parameters"]
    state = {"part_a_count": p["part_a"], "part_b_count": 0, "unassigned_a": 0, "unassigned_b": p["part_b"]}
    prompt, _ = make(question, state, "step1-v2")
    text = " ".join(json.loads(prompt.payload)["arrangement_description"])
    assert "Both collections already exist" in text and "Do not ask the learner to make" in text


def test_sharing_description_hides_share_size_and_names_people():
    question = next(q for q in QUESTIONS if q["visual"].get("recipient_labels"))
    p = question["parameters"]
    state = {"share_sizes": [5, 3, 4], "undistributed_count": 0}
    lines = describe_arrangement(question, evaluate(question, validate_workspace(question, state).workspace).facts)
    text = " ".join(lines)
    assert "Jane has 5" in text and "not equal" in text
    assert f"{p['share_size']} each" not in text


def test_v2_runs_through_the_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from app.llm.mock_client import MockClient
    from app.main import create_app
    from app.research_log import read_log

    settings = Settings(use_mock_llm=True, log_dir=tmp_path, prompt_version="step1-v2")
    client = TestClient(create_app(settings, client=MockClient(), use_default_client=False))
    payload = client.post("/api/tutor", json={"question_id": "MC-JOIN-nluds-0001", "support_type": "HINT",
                                              "learner_state": {"added_count": 0, "current_count": 7}}).json()
    assert payload["status"] == "generated"
    final = [l for l in read_log(tmp_path) if l["type"] == "final"][0]
    assert final["prompt_version"] == "step1-v2"
    assert "arrangement_description" in final["prompt_payload"]


def test_sharing_with_nothing_shared_is_not_called_equal():
    # Real run: with shares [0, 0, 0] the description said "The shares are equal",
    # and the model repeated it to the learner.
    question = next(q for q in QUESTIONS if q["interaction"] == "EQUAL_SHARING")
    n = len(question["visual"].get("recipient_labels") or []) or question["parameters"].get("recipient_count", 3)
    state = {"share_sizes": [0] * n, "undistributed_count": question["parameters"]["total"]}
    lines = describe_arrangement(question, evaluate(question, validate_workspace(question, state).workspace).facts)
    text = " ".join(lines)
    assert "Nothing has been shared yet" in text
    assert "shares are equal" not in text
