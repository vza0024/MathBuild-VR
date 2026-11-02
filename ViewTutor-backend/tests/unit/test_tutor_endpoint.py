"""/api/tutor acceptance tests (README, Phase C):

2. Lifecycle: a forced failure at every stage still gives HTTP 200 with all four
   Unity fields and exactly one final log record.
3. Evaluator priority reaches Unity correctly.
4. Every final record has the fields the analysis needs.
Plus: real Unity requests, failure kinds, at most one LLM call.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.mock_client import MockClient
from app.main import create_app
from app.research_log import read_log
from app.schemas import SUPPORT_TYPES, TutorResponse
from tests.unity_types import matches_csharp_type

JOIN_ID = "MC-JOIN-nluds-0001"   # 7 red + 2 green apples
INCOMPLETE = {"added_count": 1, "current_count": 8, "answer": None}
CORRECT = {"added_count": 2, "current_count": 9, "answer": None}


def body(state=None, support_type="HINT", **extra):
    return {"question_id": JOIN_ID, "learner_state": state or INCOMPLETE, "support_type": support_type,
            "latest_action": "", "student_message": "", "conversation_history": [], **extra}


@pytest.fixture
def make(tmp_path):
    default = object()

    def _make(client=default, use_default_client=False, **settings):
        config = Settings(use_mock_llm=True, log_dir=tmp_path / "logs", **settings)
        client = MockClient() if client is default else client
        app = create_app(config, client=client, use_default_client=use_default_client)
        return TestClient(app, raise_server_exceptions=False), tmp_path / "logs", client
    return _make


def finals(log_dir):
    return [line for line in read_log(log_dir) if line["type"] == "final"]


def assert_unity_ok(response, unity_contract):
    assert response.status_code == 200
    payload = response.json()
    for field in unity_contract["TutorResponseDto"]:
        assert field["name"] in payload
        assert matches_csharp_type(payload[field["name"]], field["type"]), field
    assert payload["tutor_response"]
    assert payload["conversation_status"] in {"continue", "correct"}
    assert payload["support_type"] in SUPPORT_TYPES
    return payload


def assert_one_final(log_dir, request_id):
    records = [f for f in finals(log_dir) if f["request_id"] == request_id]
    assert len(records) == 1, len(records)
    return records[0]


# --- Real Unity requests ---------------------------------------------------------

def test_all_logged_unity_requests(make, logged_requests, unity_contract):
    client, log_dir, _ = make()
    for logged in logged_requests:
        raw = {k: logged[k] for k in ("question_id", "support_type", "learner_state",
                                      "latest_action", "student_message")}
        payload = assert_unity_ok(client.post("/api/tutor", json=raw), unity_contract)
        assert payload["student_correct"] == logged["v4_student_correct"]
        assert payload["status"] in {"generated", "confirmed_correct", "fallback_blocked"}
    assert len(finals(log_dir)) == len(logged_requests)


# --- Acceptance test 2: lifecycle ----------------------------------------------------

def boom(*args, **kwargs):
    raise RuntimeError("forced failure")


STAGES = [
    "app.pipeline.validate_request",
    "app.pipeline.validate_workspace",
    "app.pipeline.evaluate",
    "app.pipeline.strategy_context",
    "app.pipeline.build_prompt",
    "app.pipeline.check_response",
    "app.pipeline.choose_fallback",
    "app.pipeline.confirmation",
    "app.main.handle_tutor",
]


@pytest.mark.parametrize("stage", STAGES)
def test_forced_failure_at_each_stage(make, monkeypatch, unity_contract, stage):
    client, log_dir, _ = make(client=MockClient("leak", leak_value=9))  # reaches check + fallback
    monkeypatch.setattr(stage, boom)
    state = CORRECT if stage.endswith("confirmation") else INCOMPLETE
    payload = assert_unity_ok(client.post("/api/tutor", json=body(state)), unity_contract)
    assert payload["status"] == "internal_error"
    assert payload["support_type"] == "HINT"
    record = assert_one_final(log_dir, payload["request_id"])
    assert "forced failure" in record["exception"]


def test_failure_during_response_serialization(make, monkeypatch, unity_contract):
    client, log_dir, _ = make()
    monkeypatch.setattr(TutorResponse, "model_dump_json", boom)
    payload = assert_unity_ok(client.post("/api/tutor", json=body()), unity_contract)
    assert payload["status"] == "internal_error"
    assert_one_final(log_dir, payload["request_id"])


def test_llm_client_exception(make, unity_contract):
    client, log_dir, _ = make(client=MockClient("exception"))
    payload = assert_unity_ok(client.post("/api/tutor", json=body()), unity_contract)
    assert payload["status"] == "fallback_llm_error"
    record = assert_one_final(log_dir, payload["request_id"])
    assert record["llm_failure_detail"] == "client_exception:RuntimeError"


@pytest.mark.parametrize("raw", [b"{bad json", b"", b"[1, 2]", b'"text"', b"null",
                                 b'{"question_id": "NOPE", "learner_state": {}}'])
def test_unusable_bodies(make, unity_contract, raw):
    client, log_dir, _ = make()
    payload = assert_unity_ok(client.post("/api/tutor", content=raw,
                                          headers={"Content-Type": "application/json"}), unity_contract)
    assert payload["status"] == "request_rejected"
    assert payload["support_type"] == "AUTO_CHECK"
    assert payload["tutor_response"]
    assert_one_final(log_dir, payload["request_id"])


def test_wrong_method_still_gives_200(make, unity_contract):
    client, log_dir, _ = make()
    payload = assert_unity_ok(client.get("/api/tutor"), unity_contract)
    assert payload["status"] == "internal_error"
    assert_one_final(log_dir, payload["request_id"])


def test_valid_support_type_echoed_on_rejection(make):
    client, _, _ = make()
    payload = client.post("/api/tutor", json=body(state={"added_count": "x", "current_count": 1},
                                                  support_type="CHECK_WORK")).json()
    assert payload["status"] == "workspace_rejected" and payload["support_type"] == "CHECK_WORK"
    payload = client.post("/api/tutor", json=body(support_type="MAGIC")).json()
    assert payload["status"] == "request_rejected" and payload["support_type"] == "AUTO_CHECK"


def test_no_client_configured(make):
    client, log_dir, _ = make(client=None)  # real mode without a key
    payload = client.post("/api/tutor", json=body()).json()
    assert payload["status"] == "fallback_llm_error"
    assert assert_one_final(log_dir, payload["request_id"])["llm_failure_detail"] == "llm_not_configured"


# --- Failure kinds and protection blocks ---------------------------------------------

@pytest.mark.parametrize("behavior", ["refusal", "timeout", "api_error", "incomplete_output", "invalid_output"])
def test_llm_failures_use_checked_fallback(make, behavior):
    client, log_dir, _ = make(client=MockClient(behavior))
    payload = client.post("/api/tutor", json=body()).json()
    assert payload["status"] == "fallback_llm_error"
    record = assert_one_final(log_dir, payload["request_id"])
    assert record["llm_failure"] == behavior
    assert record["fallback_passed_checks"] is True
    assert record["final_text"] == payload["tutor_response"]
    events = [e for e in read_log(log_dir) if e["type"] == "event" and e["request_id"] == payload["request_id"]]
    assert events and events[0]["event"] == "llm_result" and events[0]["failure"] == behavior


def test_leak_is_blocked_and_logged_separately(make):
    client, log_dir, _ = make(client=MockClient("leak", leak_value=9))
    payload = client.post("/api/tutor", json=body()).json()
    assert payload["status"] == "fallback_blocked"
    assert "9" not in payload["tutor_response"]
    record = assert_one_final(log_dir, payload["request_id"])
    assert record["llm_failure"] is None and record["protection_rule"]
    assert record["llm_text"].startswith("There are 9")
    events = {e["event"] for e in read_log(log_dir) if e["type"] == "event"}
    assert "blocked_by_answer_protection" in events


# --- At most one LLM call --------------------------------------------------------------

def test_one_call_per_request_and_none_when_correct(make):
    mock = MockClient()
    client, log_dir, _ = make(client=mock)
    client.post("/api/tutor", json=body())
    assert mock.calls == 1
    payload = client.post("/api/tutor", json=body(CORRECT)).json()
    assert mock.calls == 1
    assert payload["status"] == "confirmed_correct"
    assert assert_one_final(log_dir, payload["request_id"])["llm_called"] is False


# --- Acceptance test 3: evaluator priority reaches Unity -----------------------------------

@pytest.mark.parametrize("state, student_correct, construction", [
    (CORRECT, True, "correct"),
    ({**CORRECT, "answer": 8}, False, "correct"),                       # wrong entered answer
    (INCOMPLETE, False, "incomplete"),
    ({"added_count": -1, "current_count": 6}, False, "incomplete"),
    ({"added_count": 0, "current_count": 7, "part_a_count": 0, "part_b_count": 7}, False, "incorrect"),
])
def test_status_mapping(make, state, student_correct, construction):
    client, log_dir, _ = make()
    payload = client.post("/api/tutor", json=body(state)).json()
    assert payload["student_correct"] is student_correct
    assert payload["conversation_status"] == ("correct" if student_correct else "continue")
    assert assert_one_final(log_dir, payload["request_id"])["construction_status"] == construction


# --- Acceptance test 4: log completeness ----------------------------------------------------

ALWAYS = {"request_id", "timestamp", "app_version", "prompt_version", "model", "provider", "status",
          "final_text", "student_correct", "conversation_status", "total_latency_ms", "http_status"}
AFTER_EVALUATION = {"question_id", "interaction", "support_type", "construction_status", "construction_errors",
                    "answer_entered", "answer_parseable", "answer_correct", "llm_called"}
AFTER_LLM = {"llm_ok", "llm_failure", "llm_raw_output", "llm_settings", "api_latency_ms", "input_tokens",
             "output_tokens", "reasoning_tokens", "prompt_payload"}


@pytest.mark.parametrize("client_behavior, state, expect", [
    ("ok", INCOMPLETE, ALWAYS | AFTER_EVALUATION | AFTER_LLM | {"protection_rule"}),
    ("leak", INCOMPLETE, ALWAYS | AFTER_EVALUATION | AFTER_LLM | {"protection_rule", "fallback_source"}),
    ("timeout", INCOMPLETE, ALWAYS | AFTER_EVALUATION | AFTER_LLM | {"fallback_source", "fallback_passed_checks"}),
    ("ok", CORRECT, ALWAYS | AFTER_EVALUATION | {"fallback_source"}),
])
def test_final_record_fields(make, client_behavior, state, expect):
    client, log_dir, _ = make(client=MockClient(client_behavior, leak_value=9))
    payload = client.post("/api/tutor", json=body(state)).json()
    record = assert_one_final(log_dir, payload["request_id"])
    assert expect <= set(record), expect - set(record)


def test_rejected_request_still_has_core_fields(make):
    client, log_dir, _ = make()
    payload = client.post("/api/tutor", content=b"{bad").json()
    record = assert_one_final(log_dir, payload["request_id"])
    assert {"request_id", "timestamp", "status", "final_text", "rejection_reason", "total_latency_ms"} <= set(record)


def test_log_never_contains_the_key(make):
    client, log_dir, _ = make(openai_api_key="sk-secret-value")
    client.post("/api/tutor", json=body())
    for path in log_dir.glob("*.jsonl"):
        assert "sk-secret-value" not in path.read_text()


def test_view_is_logged_not_used(make):
    client, log_dir, _ = make()
    view = {"gaze_target": "tutor", "regions": [{"region_id": "basket", "visible_fraction": 0.2}]}
    with_view = client.post("/api/tutor", json=body(view=view)).json()
    without = client.post("/api/tutor", json=body()).json()
    assert with_view["tutor_response"] == without["tutor_response"]
    assert assert_one_final(log_dir, with_view["request_id"])["view"]["gaze_target"] == "tutor"
