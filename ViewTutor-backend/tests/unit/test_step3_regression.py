"""Step 3 invariants: compare actual original Step 1 implementation."""
import json
from pathlib import Path
import pytest
from app.questions import QUESTIONS
from app.sample_states import sample_states
from app.schemas import TutorRequest, ViewData
from app.validation import validate_workspace
from app.evaluator import evaluate
from app.strategies import strategy_context
from app.llm.prompts import build_prompt
from app.pipeline import handle_tutor
from app.research_log import RequestRecord
from app.config import Settings
from app.llm.client import LLMResult


def sample():
    for q in QUESTIONS:
        for _, _, state in sample_states(q):
            if validate_workspace(q, state).ok:
                return q, state
    raise AssertionError("no valid sample")


def parts(q, state):
    request = TutorRequest(question_id=q["id"], learner_state=state, support_type="HINT")
    evaluation = evaluate(q, validate_workspace(q, state).workspace)
    context = strategy_context(q, dict(evaluation.facts), "HINT")
    return request, evaluation, context


def test_baseline_byte_identical_to_step1():
    # Original module is preserved in tests/reference, not copied from the modified module.
    import importlib.util
    path = Path(__file__).parents[1] / "reference" / "step1_prompts.py"
    spec = importlib.util.spec_from_file_location("step1_reference_prompts", path)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for q in QUESTIONS:
        for _, _, state in sample_states(q):
            if not validate_workspace(q, state).ok:
                continue
            request, evaluation, context = parts(q, state)
            original = module.build_prompt(q, request, evaluation, context, "step1-v2")
            current = build_prompt(q, request, evaluation, context, "step1-v2", pov_context=None)
            assert original.instructions.encode() == current.instructions.encode(), q["id"]
            assert original.payload.encode() == current.payload.encode(), q["id"]


def test_runtime_newlines_and_no_raw_ids():
    q = next(q for q in QUESTIONS if q["interaction"] == "EQUAL_GROUPS")
    state = next(state for _, _, state in sample_states(q) if validate_workspace(q, state).ok)
    request, evaluation, context = parts(q, state)
    from app.pov_context import build_pov_context
    view = ViewData.model_validate({"regions": [{"region_id": "group_1", "visible_fraction": 1.0}]})
    pov, warnings = build_pov_context(q, view, learner_state=state)
    prompt = build_prompt(q, request, evaluation, context, pov_context=pov)
    assert "\n\nVR viewpoint guidance" in prompt.instructions
    assert "vr_pov_context" in json.loads(prompt.payload)
    assert "group_1" not in json.dumps(json.loads(prompt.payload)["vr_pov_context"])


class CaptureClient:
    def __init__(self):
        self.prompts = []
    def generate(self, prompt):
        self.prompts.append(prompt)
        return LLMResult(text="What do you notice about the groups?", raw_output='{"tutor_text":"What do you notice about the groups?"}', model="mock")


def test_pipeline_baseline_pov_and_missing_view(tmp_path):
    q = next(q for q in QUESTIONS if q["interaction"] == "EQUAL_GROUPS")
    state = next(state for _, _, state in sample_states(q) if validate_workspace(q, state).ok and not evaluate(q, validate_workspace(q, state).workspace).student_correct)
    settings = Settings(log_dir=tmp_path)
    base = {"question_id": q["id"], "support_type": "HINT", "learner_state": state,
            "view": {"regions": [{"region_id": "group_1", "visible_fraction": 1.0}]}}
    outputs = []
    for condition, raw in [("baseline", base), ("pov_aware", base), ("pov_aware", {**base, "view": None})]:
        record = RequestRecord(tmp_path)
        client = CaptureClient()
        response = handle_tutor(raw, record, settings, client, {q["id"]: q}, condition=condition)
        assert response.status not in {"request_rejected", "workspace_rejected"}
        assert client.prompts, (condition, record.fields)
        outputs.append((record.fields, client.prompts[0]))
    assert outputs[0][1].instructions == outputs[2][1].instructions
    assert outputs[0][1].payload == outputs[2][1].payload
    assert "vr_pov_context" not in json.loads(outputs[0][1].payload)
    assert "vr_pov_context" in json.loads(outputs[1][1].payload)
    assert outputs[2][0]["pov_used"] is False
    assert outputs[0][0]["construction_status"] == outputs[1][0]["construction_status"] == outputs[2][0]["construction_status"]
    assert outputs[0][0]["construction_errors"] == outputs[1][0]["construction_errors"]
