"""Plan steps 16 and 18: run scripted states through the backend and summarize.

Every scripted state (app/sample_states.py: correct, incomplete and incorrect
states per type, each physically consistent and checked by tests) is sent with
each of the 4 support types Unity sends. For every request,
`samples/step1/samples.jsonl` holds the complete input, the response, and the
matching research-log fields joined by request ID (evaluation, raw model output,
protection rule, fallback, tokens, latency), so each sample can be reviewed and
reproduced on its own.

Each run goes to its own folder (default `samples/step1/run-<UTC time>/`) and an
existing `samples.jsonl` is never overwritten, so earlier runs stay as evidence.
The script stops before sending anything if log storage is not writable, and
reports any log-write failure at the end. Compare runs with
`scripts/compare_runs.py`.

    python scripts/run_samples.py                                        # mock, free
    USE_MOCK_LLM=0 python scripts/run_samples.py --prices prices.example.json

Prices are USD per 1M tokens. `prices.example.json` is an assumption until the
account has accepted the model and the price page has been re-checked.
Reasoning tokens are part of output tokens and are not counted twice.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from fastapi.testclient import TestClient  # noqa: E402

from app import research_log  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.questions import QUESTIONS  # noqa: E402
from app.research_log import read_log, storage_check  # noqa: E402
from app.sample_states import sample_states  # noqa: E402

UNITY_SUPPORT_TYPES = ["AUTO_CHECK", "CHECK_WORK", "HINT", "SIMPLIFY_STORY"]
LOG_FIELDS = [
    "status", "construction_status", "construction_errors", "answer_entered", "answer_correct",
    "student_correct", "effective_support_type", "llm_called", "llm_ok", "llm_failure",
    "llm_failure_detail", "llm_raw_output", "llm_text", "protection_rule", "fallback_source",
    "fallback_passed_checks", "fallback_first_failed_rule", "final_text", "model", "prompt_version",
    "input_tokens", "output_tokens", "reasoning_tokens", "api_latency_ms", "total_latency_ms",
    "request_warnings", "workspace_warnings", "llm_settings",
]


def p95(values):
    values = sorted(values)
    return values[max(0, int(round(0.95 * len(values))) - 1)] if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-type", type=int, default=2, help="questions per interaction type")
    parser.add_argument("--prices", type=Path, help="JSON with input/output USD per 1M tokens")
    parser.add_argument("--model", help="override LLM_MODEL for this run (e.g. gpt-6-luna)")
    parser.add_argument("--reasoning", help="override LLM_REASONING_EFFORT for this run "
                        "(none, minimal, low, medium, high, xhigh, max; 'off' sends no reasoning setting)")
    parser.add_argument("--prompt", help="prompt version for this run: step1-v2 (default) or step1-v1")
    parser.add_argument("--out", type=Path, default=None,
                        help="output folder (default: samples/step1/run-<UTC time>; never overwritten)")
    args = parser.parse_args()
    if args.out is None:
        from datetime import datetime, timezone
        args.out = PROJECT / "samples" / "step1" / f"run-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    if (args.out / "samples.jsonl").exists():
        sys.exit(f"Stopping: {args.out / 'samples.jsonl'} already exists. Earlier runs are kept as evidence; "
                 f"choose another --out.")

    settings = load_settings()
    log_dir = args.out / "logs"
    overrides = {"log_dir": log_dir}
    if args.model:
        overrides["llm_model"] = args.model
    if args.prompt:
        overrides["prompt_version"] = args.prompt
    if args.reasoning:
        overrides["llm_reasoning_effort"] = "" if args.reasoning == "off" else args.reasoning
    settings = type(settings)(**{**settings.__dict__, **overrides})
    ok, error = storage_check(log_dir)
    if not ok:
        sys.exit(f"Stopping: research log storage is not writable ({error}).")
    failures_before = research_log.WRITE_FAILURES
    client = TestClient(create_app(settings))
    args.out.mkdir(parents=True, exist_ok=True)

    chosen = []
    for interaction in ("JOIN", "REMOVE", "EQUAL_GROUPS", "EQUAL_SHARING", "PART_TO_PART_RATIO"):
        chosen += [q for q in QUESTIONS if q["interaction"] == interaction][: args.per_type]

    sent = []
    for q in chosen:
        for label, expected, state in sample_states(q):
            for support_type in UNITY_SUPPORT_TYPES:
                request = {"question_id": q["id"], "learner_state": state, "support_type": support_type,
                           "latest_action": "", "student_message": "", "conversation_history": []}
                response = client.post("/api/tutor", json=request)
                sent.append({"question_id": q["id"], "interaction": q["interaction"], "story": q["body"],
                             "question": q["question"], "state_label": label,
                             "expected_construction_status": expected, "request": request,
                             "response": response.json(),
                             "research_log_written": response.headers.get("X-Research-Log")})

    finals = {f["request_id"]: f for f in read_log(log_dir) if f["type"] == "final"}
    mismatched_status = 0
    with (args.out / "samples.jsonl").open("w", encoding="utf-8") as out:
        for sample in sent:
            record = finals.get(sample["response"]["request_id"], {})
            sample["log"] = {key: record.get(key) for key in LOG_FIELDS}
            if record.get("construction_status") != sample["expected_construction_status"]:
                mismatched_status += 1
            out.write(json.dumps(sample, ensure_ascii=False) + "\n")

    records = [finals[s["response"]["request_id"]] for s in sent if s["response"]["request_id"] in finals]
    statuses = Counter(r["status"] for r in records)
    api = [r["api_latency_ms"] for r in records if r.get("api_latency_ms") is not None]
    total = [r["total_latency_ms"] for r in records]
    tokens_in = sum(r.get("input_tokens") or 0 for r in records)
    tokens_out = sum(r.get("output_tokens") or 0 for r in records)
    calls = sum(1 for r in records if r.get("llm_called"))
    print(f"requests: {len(sent)}   final records: {len(records)}   LLM calls: {calls}")
    print(f"provider: {settings.provider}   model: {settings.model_id}   "
          f"reasoning: {settings.llm_reasoning_effort or 'not sent'}   prompt: {settings.prompt_version}")
    print("statuses:", dict(statuses))
    print("protection rules fired:", dict(Counter(r["protection_rule"] for r in records if r.get("protection_rule"))))
    print("LLM failures:", dict(Counter(r["llm_failure"] for r in records if r.get("llm_failure"))))
    if api:
        print(f"API latency ms: mean {statistics.mean(api):.0f}, p95 {p95(api):.0f}")
    if total:
        print(f"total latency ms: mean {statistics.mean(total):.0f}, p95 {p95(total):.0f}")
    print(f"tokens: input {tokens_in}, output {tokens_out}")
    if args.prices and calls:
        prices = json.loads(args.prices.read_text())
        cost = tokens_in / 1e6 * prices["input"] + tokens_out / 1e6 * prices["output"]
        print(f"cost (assumed prices): ${cost:.4f} total, ${cost / calls:.5f} per LLM call")
    problems = []
    if research_log.WRITE_FAILURES > failures_before or len(records) != len(sent):
        problems.append(f"log write failures: {research_log.WRITE_FAILURES - failures_before}, "
                        f"missing final records: {len(sent) - len(records)}")
    if mismatched_status:
        problems.append(f"{mismatched_status} samples did not get their expected construction status")
    print(f"samples: {args.out / 'samples.jsonl'}   logs: {log_dir}")
    if problems:
        sys.exit("PROBLEMS: " + "; ".join(problems))


if __name__ == "__main__":
    main()
