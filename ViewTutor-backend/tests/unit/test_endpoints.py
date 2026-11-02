"""/api/health and /api/questions against Unity's DTOs."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.main import build_health
from tests.unity_types import matches_csharp_type


def check_against_dto(payload: dict, dto_fields: list[dict[str, str]]) -> None:
    for field in dto_fields:
        name, csharp_type = field["name"], field["type"]
        value = payload.get(name)
        assert matches_csharp_type(value, csharp_type), f"{name}: {value!r} is not {csharp_type}"


def test_health_matches_unity_dto(client, unity_contract):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    dto = unity_contract["HealthResponseDto"]
    assert {f["name"] for f in dto} <= set(payload)
    check_against_dto(payload, dto)
    assert payload["status"] == "ok"
    assert payload["question_count"] == 88
    assert payload["llm_provider"] == "mock"
    assert payload["gpu_available"] is False


def test_health_reports_missing_key():
    health = build_health(Settings(openai_api_key="", use_mock_llm=False))
    assert health.llm_configured is False
    assert health.model_error
    assert "sk-" not in health.model_dump_json()


def test_health_never_contains_key():
    health = build_health(Settings(openai_api_key="sk-very-secret", use_mock_llm=False, llm_model="m"))
    assert "sk-very-secret" not in health.model_dump_json()


def test_questions_not_empty_and_all_types(client):
    payload = client.get("/api/questions").json()
    assert isinstance(payload, list) and len(payload) == 88
    assert {q["interaction"] for q in payload} == {
        "JOIN", "REMOVE", "EQUAL_GROUPS", "EQUAL_SHARING", "PART_TO_PART_RATIO",
    }


def test_questions_match_unity_dtos(client, unity_contract):
    payload = client.get("/api/questions").json()
    for question in payload:
        check_against_dto(question, unity_contract["QuestionDto"])
        check_against_dto(question["parameters"], unity_contract["QuestionParametersDto"])
        check_against_dto(question["visual"], unity_contract["QuestionVisualDto"])


@pytest.mark.parametrize("path", ["/api/health", "/api/questions"])
def test_get_endpoints_return_200(client, path):
    assert client.get(path).status_code == 200
