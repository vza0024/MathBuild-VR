"""Log-storage failures are visible; conservation mismatches are warnings."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import research_log
from app.config import Settings
from app.llm.mock_client import MockClient
from app.main import create_app
from app.questions import QUESTION_BY_ID
from app.research_log import read_log, storage_check
from app.validation import validate_workspace

BODY = {"question_id": "MC-JOIN-nluds-0001", "learner_state": {"added_count": 1, "current_count": 8},
        "support_type": "HINT"}


def test_healthy_storage(tmp_path):
    client = TestClient(create_app(Settings(use_mock_llm=True, log_dir=tmp_path / "logs"), client=MockClient()))
    response = client.post("/api/tutor", json=BODY)
    assert response.headers["X-Research-Log"] == "ok"
    health = client.get("/api/health").json()
    assert health["log_storage_ok"] is True
    assert list((tmp_path / "logs").glob(".probe-*")) == []   # probe file removed


def test_unwritable_storage_is_signalled_but_response_still_works(tmp_path):
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("x")                     # a file where the log directory should be
    log_dir = blocker / "logs"
    before = research_log.WRITE_FAILURES
    client = TestClient(create_app(Settings(use_mock_llm=True, log_dir=log_dir), client=MockClient()))
    response = client.post("/api/tutor", json=BODY)
    assert response.status_code == 200 and response.json()["tutor_response"]
    assert response.headers["X-Research-Log"] == "failed"
    assert research_log.WRITE_FAILURES > before
    health = client.get("/api/health").json()
    assert health["log_storage_ok"] is False and health["log_write_failures"] >= 1
    assert health["log_storage_error"]
    assert storage_check(log_dir)[0] is False


def test_conservation_mismatch_is_a_warning_not_a_rejection(tmp_path):
    question = next(q for q in QUESTION_BY_ID.values() if q["interaction"] == "REMOVE")
    initial = question["parameters"]["initial"]
    check = validate_workspace(question, {"removed_count": 1, "remaining_count": initial + 5})
    assert check.ok and check.warnings == ["remove_total_differs_from_initial"]

    client = TestClient(create_app(Settings(use_mock_llm=True, log_dir=tmp_path), client=MockClient()))
    payload = client.post("/api/tutor", json={"question_id": question["id"], "support_type": "HINT",
                                              "learner_state": {"removed_count": 1,
                                                                "remaining_count": initial + 5}}).json()
    assert payload["status"] != "workspace_rejected"
    final = [line for line in read_log(tmp_path) if line["type"] == "final"][0]
    assert final["workspace_warnings"] == ["remove_total_differs_from_initial"]


def test_conservation_checks_per_type():
    sharing = next(q for q in QUESTION_BY_ID.values() if q["interaction"] == "EQUAL_SHARING")
    n = sharing["parameters"]["recipient_count"]
    assert validate_workspace(sharing, {"share_sizes": [0] * n, "undistributed_count": 999}).warnings == [
        "sharing_total_differs_from_story"]
    ratio = next(q for q in QUESTION_BY_ID.values() if q["interaction"] == "PART_TO_PART_RATIO")
    warnings = validate_workspace(ratio, {"part_a_count": 0, "part_b_count": 0, "unassigned_a": 0,
                                          "unassigned_b": 0}).warnings
    assert warnings == ["ratio_part_a_total_differs_from_story", "ratio_part_b_total_differs_from_story"]
    groups = next(q for q in QUESTION_BY_ID.values() if q["interaction"] == "EQUAL_GROUPS")
    assert validate_workspace(groups, {"group_sizes": [1], "undistributed_count": 999}).warnings == []
