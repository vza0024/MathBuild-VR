"""Deterministic mock LLM. Default in development and in all unit tests.

Makes no network calls and costs nothing. Returns a fixed, plausible reply per
support type, built from the prompt payload. `behavior` forces a specific
outcome so every pipeline path can be tested:

  ok          plausible reply (still checked by answer protection)
  leak        a reply that states the hidden answer (needs `leak_value`)
  refusal | timeout | api_error | incomplete_output | invalid_output   the matching failure
  exception   raises, to prove the pipeline survives a broken client
"""
from __future__ import annotations

import json
from typing import Optional

from app.llm.client import LLMResult
from app.llm.prompts import Prompt

MOCK_SETTINGS = {"provider": "mock", "model": "mock", "max_retries": 0}


def _reply(payload: dict) -> str:
    support = payload.get("support_request")
    visual = payload.get("object_language") or {}
    objects = visual.get("object_plural") or "objects"
    if support == "SIMPLIFY_STORY":
        return f"The story tells what happens to the {objects}. Show each part of the story with the objects."
    if support == "CHECK_WORK":
        return f"Compare the {objects} in your arrangement with the story. What do you notice?"
    if support == "UNSURE":
        return f"It is okay to be unsure. Compare one part of your {objects} with the story."
    if support == "INTERFACE_HELP":
        return "Drag an object from the object bank to where you want it to go. Undo reverses the last move."
    if support == "SMALLER_EXAMPLE":
        example = payload.get("smaller_example") or {}
        return (f"Try a smaller example: imagine {example.get('first')} counters and "
                f"{example.get('second')} counters. Build it, but leave the result unanswered.")
    if support == "OPEN_ENDED":
        return f"Let us look at your {objects} together. Compare one part of the arrangement with the story."
    # HINT and AUTO_CHECK
    return f"Look at the {objects} in your arrangement and compare one part with the story."


class MockClient:
    def __init__(self, behavior: str = "ok", leak_value: Optional[int] = None):
        self.behavior = behavior
        self.leak_value = leak_value
        self.calls = 0

    def generate(self, prompt: Prompt) -> LLMResult:
        self.calls += 1
        result = LLMResult(model="mock", settings=dict(MOCK_SETTINGS), api_latency_ms=0.0)
        if self.behavior == "exception":
            raise RuntimeError("mock client failure")
        if self.behavior in {"refusal", "timeout", "api_error", "incomplete_output", "invalid_output"}:
            result.failure = self.behavior  # type: ignore[assignment]
            result.failure_detail = "forced by mock"
            if self.behavior == "invalid_output":
                result.raw_output = "{not json"
            return result
        payload = json.loads(prompt.payload)
        if self.behavior == "leak":
            objects = (payload.get("object_language") or {}).get("object_plural") or "objects"
            text = f"There are {self.leak_value} {objects} altogether."
        else:
            text = _reply(payload)
        result.raw_output = json.dumps({"tutor_text": text})
        result.text = text
        return result
