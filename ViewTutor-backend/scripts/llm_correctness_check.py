"""Can the LLM judge correctness instead of Python? Measure it.

For each scripted learner state (app/sample_states.py), the model gets the same
information a tutor would have: the story, the question, and the learner's
construction. It is asked to classify the construction as correct, incomplete or
incorrect. Its answer is compared with the deterministic evaluator
(app/evaluator.py), which is exact arithmetic on the question's stated quantities.

Reported per model / reasoning effort:
  accuracy               share of states where the model agrees with the evaluator
  false "correct"        model says correct when the work is not (the costly error:
                         the app would end the task on a wrong construction)
  missed "correct"       model says not correct when the work is correct
  confusion table        evaluator status vs model status
  latency mean / p95, tokens, failures

    python scripts/llm_correctness_check.py --per-type 2
    python scripts/llm_correctness_check.py --model gpt-6-luna --reasoning none

Results go to samples/correctness/run-<UTC time>/ (never overwritten).
Needs OPENAI_API_KEY in .env. This script does not use USE_MOCK_LLM: it always
calls the API, and only the backend's own correctness check is used in the app.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from app.config import load_settings  # noqa: E402
from app.evaluator import evaluate  # noqa: E402
from app.questions import QUESTIONS, student_safe  # noqa: E402
from app.sample_states import sample_states  # noqa: E402
from app.validation import validate_workspace  # noqa: E402

STATUSES = ("correct", "incomplete", "incorrect")
SCHEMA = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": list(STATUSES)}},
    "required": ["status"],
    "additionalProperties": False,
}
INSTRUCTIONS = """You check a child's work in a virtual-reality math activity. The child builds the story with objects.
Classify the construction:
- "correct": finished and exactly matches the story.
- "incorrect": contains a definite error, even if unfinished (e.g. a group already has more than the story says).
- "incomplete": not finished yet, but nothing is wrong so far.
Counts in the learner state are only what the child has physically placed.
Return JSON {"status": "..."}."""

FIELD_NOTES = {
    "JOIN": "added_count = objects added beyond the starting amount (negative if starting objects were moved out); "
            "current_count = objects in the collection; part_a_count / part_b_count, when present, are the two kinds.",
    "REMOVE": "removed_count = objects in the removed area; remaining_count = objects left.",
    "EQUAL_GROUPS": "group_sizes = objects in each group built so far; undistributed_count = objects left in the tray.",
    "EQUAL_SHARING": "share_sizes = objects each recipient has; undistributed_count = objects not yet shared.",
    "PART_TO_PART_RATIO": "part_a_count / part_b_count = objects in the first / second collection; "
                          "unassigned_a / unassigned_b = objects of each kind not yet placed.",
}


def build_input(question: dict[str, Any], state: dict[str, Any]) -> str:
    safe = student_safe(question)
    return json.dumps({
        "story": question["body"],
        "question": question["question"],
        "interaction": question["interaction"],
        "object_language": question.get("visual", {}),
        "learner_state": {k: v for k, v in state.items() if k != "answer"},
        "learner_state_fields": FIELD_NOTES[question["interaction"]],
        "visible_story_quantities": safe["parameters"],
    }, ensure_ascii=False)


def parse_status(raw: str) -> Optional[str]:
    try:
        value = json.loads(raw).get("status")
    except (TypeError, ValueError, AttributeError):
        return None
    return value if value in STATUSES else None


def p95(values: list[float]) -> Optional[float]:
    values = sorted(values)
    return values[max(0, int(round(0.95 * len(values))) - 1)] if values else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [r for r in rows if r["model_status"] is not None]
    agree = sum(r["model_status"] == r["python_status"] for r in judged)
    false_correct = sum(r["model_status"] == "correct" and r["python_status"] != "correct" for r in judged)
    not_correct = sum(r["python_status"] != "correct" for r in judged)
    missed_correct = sum(r["python_status"] == "correct" and r["model_status"] != "correct" for r in judged)
    correct = sum(r["python_status"] == "correct" for r in judged)
    latency = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    confusion = Counter((r["python_status"], r["model_status"]) for r in judged)
    by_type = {}
    for interaction in sorted({r["interaction"] for r in judged}):
        sub = [r for r in judged if r["interaction"] == interaction]
        by_type[interaction] = f"{sum(r['model_status'] == r['python_status'] for r in sub)}/{len(sub)}"
    return {
        "states": len(rows),
        "failures": len(rows) - len(judged),
        "accuracy": f"{agree}/{len(judged)}" + (f" ({agree / len(judged):.0%})" if judged else ""),
        "false_correct": f"{false_correct}/{not_correct}",
        "missed_correct": f"{missed_correct}/{correct}",
        "accuracy_by_type": by_type,
        "confusion (python -> model)": {f"{a} -> {b}": n for (a, b), n in sorted(confusion.items())},
        "latency_ms": (f"mean {statistics.mean(latency):.0f}, p95 {p95(latency):.0f}" if latency else "n/a"),
        "output_tokens_per_call": (f"{statistics.mean(o):.0f}" if (o := [r["output_tokens"] for r in rows
                                                                       if r["output_tokens"]]) else "n/a"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-type", type=int, default=2, help="questions per interaction type")
    parser.add_argument("--model", help="model (default: LLM_MODEL from .env)")
    parser.add_argument("--reasoning", help="reasoning effort, or 'off' to send none (default: .env)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    settings = load_settings()
    if not settings.openai_api_key:
        sys.exit("Stopping: OPENAI_API_KEY is not set in .env.")
    model = args.model or settings.llm_model
    effort = settings.llm_reasoning_effort if args.reasoning is None else ("" if args.reasoning == "off" else args.reasoning)
    out = args.out or PROJECT / "samples" / "correctness" / f"run-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    if (out / "results.jsonl").exists():
        sys.exit(f"Stopping: {out / 'results.jsonl'} already exists; choose another --out.")
    out.mkdir(parents=True, exist_ok=True)

    import openai
    client = openai.OpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_s, max_retries=0)

    chosen = []
    for interaction in ("JOIN", "REMOVE", "EQUAL_GROUPS", "EQUAL_SHARING", "PART_TO_PART_RATIO"):
        chosen += [q for q in QUESTIONS if q["interaction"] == interaction][: args.per_type]

    rows = []
    with (out / "results.jsonl").open("w", encoding="utf-8") as handle:
        for question in chosen:
            for label, _, state in sample_states(question):
                python_status = evaluate(question, validate_workspace(question, state).workspace).construction_status
                kwargs: dict[str, Any] = {
                    "model": model, "instructions": INSTRUCTIONS, "input": build_input(question, state),
                    "max_output_tokens": settings.llm_max_output_tokens, "store": False,
                    "text": {"format": {"type": "json_schema", "name": "correctness", "schema": SCHEMA,
                                        "strict": True}},
                }
                if effort:
                    kwargs["reasoning"] = {"effort": effort}
                start = time.perf_counter()
                row = {"question_id": question["id"], "interaction": question["interaction"],
                       "state_label": label, "learner_state": state, "python_status": python_status,
                       "model": model, "reasoning_effort": effort or None, "model_status": None,
                       "raw": None, "error": None, "latency_ms": None, "output_tokens": None}
                try:
                    response = client.responses.create(**kwargs)
                    row["latency_ms"] = (time.perf_counter() - start) * 1000
                    row["raw"] = getattr(response, "output_text", None)
                    row["model_status"] = parse_status(row["raw"])
                    usage = getattr(response, "usage", None)
                    row["output_tokens"] = getattr(usage, "output_tokens", None) if usage else None
                    if row["model_status"] is None:
                        row["error"] = f"unparsable output (status={getattr(response, 'status', None)})"
                except Exception as exc:
                    row["latency_ms"] = (time.perf_counter() - start) * 1000
                    row["error"] = f"{type(exc).__name__}: {exc}"[:300]
                rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = summarize(rows)
    summary["model"], summary["reasoning_effort"] = model, effort or "not sent"
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    for key, value in summary.items():
        print(f"{key:30} {value}")
    print(f"results: {out / 'results.jsonl'}")


if __name__ == "__main__":
    main()
