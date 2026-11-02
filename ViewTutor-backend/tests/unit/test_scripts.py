"""Offline checks for the benchmark scripts (no API calls)."""
from __future__ import annotations

import json
import os

from scripts.llm_correctness_check import build_input, parse_status, summarize
from app.questions import QUESTIONS
from app.sample_states import sample_states


def test_correctness_input_hides_the_answer():
    for question in QUESTIONS:
        for _, _, state in sample_states(question):
            payload = json.loads(build_input(question, state))
            assert "answer" not in payload and "formula" not in json.dumps(payload)
            hidden = {"EQUAL_GROUPS": "total", "EQUAL_SHARING": "share_size"}.get(question["interaction"])
            if hidden:
                assert hidden not in payload["visible_story_quantities"]


def test_parse_status():
    assert parse_status('{"status": "correct"}') == "correct"
    assert parse_status('{"status": "done"}') is None
    assert parse_status("nope") is None


def test_summary_counts_costly_errors():
    rows = [
        {"interaction": "JOIN", "python_status": "correct", "model_status": "correct", "latency_ms": 1, "output_tokens": 5},
        {"interaction": "JOIN", "python_status": "incorrect", "model_status": "correct", "latency_ms": 2, "output_tokens": 5},
        {"interaction": "JOIN", "python_status": "incomplete", "model_status": "incomplete", "latency_ms": 3, "output_tokens": 5},
        {"interaction": "JOIN", "python_status": "correct", "model_status": None, "latency_ms": 4, "output_tokens": None},
    ]
    s = summarize(rows)
    assert s["accuracy"].startswith("2/3")
    assert s["false_correct"] == "1/2"
    assert s["missed_correct"] == "0/1"
    assert s["failures"] == 1


def test_run_samples_accepts_model_and_reasoning(tmp_path):
    import subprocess, sys
    out = tmp_path / "run"
    result = subprocess.run([sys.executable, "scripts/run_samples.py", "--per-type", "1", "--model", "x-model",
                             "--reasoning", "medium", "--out", str(out)],
                            capture_output=True, text=True, env={**os.environ, "USE_MOCK_LLM": "1"})
    assert result.returncode == 0, result.stderr
    assert "reasoning: medium" in result.stdout
