"""Settings: safe defaults, key never exposed."""
from __future__ import annotations

import pytest

from app.config import Settings, load_settings


def test_defaults_never_spend_money(monkeypatch):
    for name in ("OPENAI_API_KEY", "USE_MOCK_LLM", "LLM_MODEL", "LLM_TIMEOUT_S"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.use_mock_llm is True
    assert settings.provider == "mock"
    assert settings.model_id == "mock"


def test_key_is_not_in_repr():
    settings = Settings(openai_api_key="sk-test-secret", use_mock_llm=False)
    assert "sk-test-secret" not in repr(settings)


def test_real_mode_reports_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("USE_MOCK_LLM", "0")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    settings = load_settings()
    assert settings.provider == "openai"
    assert settings.model_id == "some-model"
    assert settings.llm_configured is True


def test_real_mode_without_key_is_not_configured():
    settings = Settings(openai_api_key="", use_mock_llm=False)
    assert settings.llm_configured is False


def test_bad_integer_setting_fails_loudly(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "twenty")
    with pytest.raises(ValueError, match="LLM_TIMEOUT_S"):
        load_settings()


def test_relative_log_dir_is_inside_project(monkeypatch):
    from app.config import PROJECT_DIR

    monkeypatch.setenv("LOG_DIR", "logs")
    assert load_settings().log_dir == PROJECT_DIR / "logs"
