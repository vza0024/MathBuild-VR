"""Prompt, OpenAI client (with a fake SDK) and mock client. No network calls."""
from __future__ import annotations

import json
from types import SimpleNamespace

import openai
import pytest

from app.config import Settings
from app.evaluator import evaluate, hidden_answer
from app.llm.client import OUTPUT_SCHEMA, OpenAIClient, parse_output
from app.llm.mock_client import MockClient
from app.llm.prompts import PROMPT_VERSION, build_prompt
from app.questions import QUESTIONS, student_safe
from app.schemas import SUPPORT_TYPES, TutorRequest
from app.strategies import strategy_context
from app.validation import validate_workspace

NEUTRAL = {
    "JOIN": {"added_count": 0, "current_count": 0},
    "REMOVE": {"removed_count": 0, "remaining_count": 0},
    "EQUAL_GROUPS": {"group_sizes": [], "undistributed_count": 0},
    "EQUAL_SHARING": {"share_sizes": [], "undistributed_count": 0},
    "PART_TO_PART_RATIO": {"part_a_count": 0, "part_b_count": 0, "unassigned_a": 0, "unassigned_b": 0},
}


def make_prompt(question, support_type="HINT", state=None, message=""):
    state = state or NEUTRAL[question["interaction"]]
    request = TutorRequest(question_id=question["id"], learner_state=state, support_type=support_type,
                           student_message=message)
    evaluation = evaluate(question, validate_workspace(question, state).workspace)
    context = strategy_context(question, dict(evaluation.facts), support_type)
    return build_prompt(question, request, evaluation, context)


# --- Prompt never carries the hidden answer --------------------------------------

FORBIDDEN_KEYS = {"answer", "formula", "expected_answer", "expected_final_count", "expected_total",
                  "expected_share_size", "expected_remaining_count", "work_answer"}


def _keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from _keys(v)


def _numbers(value):
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _numbers(v)


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_prompt_payload_hides_answer(question):
    for support_type in SUPPORT_TYPES:
        prompt = make_prompt(question, support_type)
        payload = json.loads(prompt.payload)
        assert not FORBIDDEN_KEYS & set(_keys(payload)), support_type
        answer = hidden_answer(question)
        stated = {v for v in student_safe(question)["parameters"].values() if isinstance(v, int)}
        structured = set(_numbers({k: v for k, v in payload.items() if k != "problem"}))
        # The answer value may only appear where the story states it openly.
        if answer in structured:
            assert answer in stated or support_type == "SMALLER_EXAMPLE", (support_type, answer)


def test_prompt_is_versioned_and_includes_status():
    prompt = make_prompt(QUESTIONS[0])
    payload = json.loads(prompt.payload)
    assert prompt.version == PROMPT_VERSION
    assert payload["construction_status"] in {"correct", "incomplete", "incorrect"}
    assert "Never decide yourself whether the work is correct" in prompt.instructions


def test_prompt_includes_state_note_when_sent():
    question = QUESTIONS[0]
    state = {**NEUTRAL["JOIN"], "state_note": "Counts are only what the learner placed."}
    assert json.loads(make_prompt(question, state=state).payload)["state_note"].startswith("Counts")


def test_change_unknown_join_gets_extra_guidance():
    question = next(q for q in QUESTIONS if q["interaction"] == "JOIN" and q["unknown_position"] == "CHANGE")
    assert "hides how many objects joined" in make_prompt(question).instructions


# --- Output parsing ----------------------------------------------------------------

@pytest.mark.parametrize("raw, text, problem", [
    ('{"tutor_text": "Look again."}', "Look again.", None),
    ('{"tutor_text": "  Look\\n again. "}', "Look again.", None),
    ('{"tutor_text": ""}', None, "tutor_text_empty"),
    ('{"tutor_text": 5}', None, "tutor_text_missing"),
    ('{"other": "x"}', None, "tutor_text_missing"),
    ('["x"]', None, "not_object"),
    ("not json", None, "not_json"),
    (None, None, "not_json"),
])
def test_parse_output(raw, text, problem):
    assert parse_output(raw) == (text, problem)


def test_schema_is_strict():
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert OUTPUT_SCHEMA["required"] == ["tutor_text"]


# --- OpenAI client with a fake SDK ---------------------------------------------------

class FakeResponses:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def fake_response(text='{"tutor_text": "Look at the apples."}', status="completed", refusal=None,
                  incomplete_reason=None):
    content = [SimpleNamespace(type="refusal", refusal=refusal)] if refusal else \
        [SimpleNamespace(type="output_text", text=text)]
    return SimpleNamespace(
        id="resp_1", model="test-model", status=status, output_text="" if refusal else text,
        output=[SimpleNamespace(type="message", content=content)],
        incomplete_details=SimpleNamespace(reason=incomplete_reason) if incomplete_reason else None,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20,
                              output_tokens_details=SimpleNamespace(reasoning_tokens=5)),
    )


def client_with(outcome, **settings):
    fake = SimpleNamespace(responses=FakeResponses(outcome))
    config = Settings(openai_api_key="sk-test", use_mock_llm=False, llm_model="test-model", **settings)
    return OpenAIClient(config, sdk_client=fake), fake.responses


def test_success_records_usage_and_one_call():
    client, responses = client_with(fake_response())
    result = client.generate(make_prompt(QUESTIONS[0]))
    assert result.ok and result.text == "Look at the apples."
    assert (result.input_tokens, result.output_tokens, result.reasoning_tokens) == (100, 20, 5)
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["text"]["format"]["strict"] is True
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert result.settings["max_retries"] == 0
    assert "sk-test" not in json.dumps(result.to_log())


def test_reasoning_omitted_when_not_configured():
    client, responses = client_with(fake_response(), llm_reasoning_effort="")
    client.generate(make_prompt(QUESTIONS[0]))
    assert "reasoning" not in responses.calls[0]


@pytest.mark.parametrize("outcome, failure", [
    (fake_response(refusal="I can't help with that."), "refusal"),
    (fake_response(status="incomplete", incomplete_reason="max_output_tokens"), "incomplete_output"),
    (fake_response(text="not json"), "invalid_output"),
    (fake_response(text='{"tutor_text": ""}'), "invalid_output"),
    (openai.APITimeoutError(request=None), "timeout"),
    (openai.APIConnectionError(request=None), "api_error"),
    (RuntimeError("boom"), "api_error"),
])
def test_failures_are_classified_and_never_raise(outcome, failure):
    client, responses = client_with(outcome)
    result = client.generate(make_prompt(QUESTIONS[0]))
    assert not result.ok
    assert result.failure == failure
    assert len(responses.calls) == 1   # no retry


def test_sdk_client_built_without_retries(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    OpenAIClient(Settings(openai_api_key="sk-x", use_mock_llm=False, llm_timeout_s=7))
    assert captured["max_retries"] == 0 and captured["timeout"] == 7


# --- Mock client ----------------------------------------------------------------------

@pytest.mark.parametrize("support_type", SUPPORT_TYPES)
def test_mock_replies_for_every_support_type(support_type):
    result = MockClient().generate(make_prompt(QUESTIONS[0], support_type))
    assert result.ok and result.model == "mock"


@pytest.mark.parametrize("behavior", ["refusal", "timeout", "api_error", "incomplete_output", "invalid_output"])
def test_mock_forced_failures(behavior):
    result = MockClient(behavior).generate(make_prompt(QUESTIONS[0]))
    assert result.failure == behavior and not result.ok


def test_mock_exception_and_leak():
    with pytest.raises(RuntimeError):
        MockClient("exception").generate(make_prompt(QUESTIONS[0]))
    leak = MockClient("leak", leak_value=9).generate(make_prompt(QUESTIONS[0]))
    assert "9" in leak.text
