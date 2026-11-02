"""Real OpenAI calls. Skipped unless OPENAI_API_KEY is set and USE_MOCK_LLM=0.

Run only after every unit test passes:
    python -m pytest tests/unit && python -m pytest tests/integration
Five requests in total (one per interaction type), so the cost is small.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app
from app.questions import QUESTIONS
from app.research_log import read_log

STATES = {
    "JOIN": {"added_count": 0, "current_count": 0},
    "REMOVE": {"removed_count": 0, "remaining_count": 0},
    "EQUAL_GROUPS": {"group_sizes": [], "undistributed_count": 0},
    "EQUAL_SHARING": {"share_sizes": [], "undistributed_count": 0},
    "PART_TO_PART_RATIO": {"part_a_count": 0, "part_b_count": 0, "unassigned_a": 0, "unassigned_b": 0},
}


@pytest.mark.parametrize("interaction", list(STATES))
def test_one_real_hint_per_interaction(tmp_path, interaction):
    settings = load_settings()
    settings = type(settings)(**{**settings.__dict__, "log_dir": tmp_path})
    client = TestClient(create_app(settings))
    question = next(q for q in QUESTIONS if q["interaction"] == interaction)
    payload = client.post("/api/tutor", json={
        "question_id": question["id"], "learner_state": STATES[interaction], "support_type": "HINT",
    }).json()
    assert payload["status"] in {"generated", "fallback_blocked", "fallback_llm_error"}
    final = [line for line in read_log(tmp_path) if line["type"] == "final"][0]
    # A real call happened and was logged, whatever its outcome.
    assert final["llm_called"] is True
    assert final["llm_settings"]["provider"] == "openai"
    if final["llm_ok"]:
        assert final["input_tokens"] and final["output_tokens"]
