"""Shared test fixtures.

Unit tests (tests/unit) never call the real API. Integration tests
(tests/integration) are skipped automatically unless OPENAI_API_KEY is set
and USE_MOCK_LLM is off; run them only after every unit test passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_DIR / "tests" / "fixtures"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.config import Settings  # noqa: E402


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Settings that can never reach the real API."""
    return Settings(openai_api_key="", use_mock_llm=True, log_dir=tmp_path / "logs")


@pytest.fixture
def client(mock_settings: Settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app(mock_settings))


@pytest.fixture(scope="session")
def logged_requests() -> list[dict[str, Any]]:
    """145 real Unity requests recorded by v4, with v4's outcome."""
    path = FIXTURES / "v4_logged_requests.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="session")
def unity_contract() -> dict[str, list[dict[str, str]]]:
    """Field names and C# types extracted from Unity's Networking/DTOs."""
    return json.loads((FIXTURES / "unity_contract.json").read_text(encoding="utf-8"))


def pytest_collection_modifyitems(config, items):
    from app.config import load_settings

    settings = load_settings()
    if settings.openai_api_key and not settings.use_mock_llm:
        return
    skip = pytest.mark.skip(reason="integration tests need OPENAI_API_KEY and USE_MOCK_LLM=0")
    for item in items:
        if "tests/integration" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip)
