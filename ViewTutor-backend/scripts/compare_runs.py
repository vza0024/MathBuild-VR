"""Compare sample runs: protection blocks, fallbacks, and how revealing the replies are.

    python scripts/compare_runs.py samples/step1/samples.jsonl samples/step1/run-*/samples.jsonl

For each run: number of requests, LLM calls, statuses, block rate (blocked / LLM
replies), fallback rate, the protection rules that fired, and disclosure:
how often the text the child heard states an exact move ("Move 2 more cookies"),
for generated replies and for fallbacks separately. Mean and p95 API latency.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.fallback import states_exact_move  # noqa: E402


def p95(values):
    values = sorted(values)
    return values[max(0, int(round(0.95 * len(values))) - 1)] if values else None


def summarize(path: Path) -> dict:
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    logs = [s["log"] for s in samples]
    status = Counter(log["status"] for log in logs)
    llm_replies = sum(1 for log in logs if log.get("llm_ok"))
    blocked = status.get("fallback_blocked", 0)
    fallbacks = blocked + status.get("fallback_llm_error", 0)
    generated = [log for log in logs if log["status"] == "generated"]
    fallback_logs = [log for log in logs if log["status"] in {"fallback_blocked", "fallback_llm_error"}]
    api = [log["api_latency_ms"] for log in logs if log.get("api_latency_ms")]
    return {
        "requests": len(samples),
        "llm_calls": sum(1 for log in logs if log.get("llm_called")),
        "statuses": dict(status),
        "block_rate": f"{blocked}/{llm_replies}" + (f" ({blocked / llm_replies:.0%})" if llm_replies else ""),
        "fallback_rate": f"{fallbacks}/{len(samples)}",
        "rules_fired": dict(Counter(log["protection_rule"] for log in logs if log.get("protection_rule"))),
        "exact_move_in_generated": f"{sum(states_exact_move(l['final_text']) for l in generated)}/{len(generated)}",
        "exact_move_in_fallbacks": f"{sum(states_exact_move(l['final_text']) for l in fallback_logs)}/{len(fallback_logs)}",
        "exact_move_in_blocked_llm_text": f"{sum(states_exact_move(l.get('llm_text') or '') for l in logs if l['status'] == 'fallback_blocked')}/{blocked}",
        "api_latency_ms": (f"mean {statistics.mean(api):.0f}, p95 {p95(api):.0f}" if api else "n/a"),
        "models": dict(Counter(log.get("model") for log in logs)),
        "reasoning_effort": dict(Counter((s.get("log", {}).get("llm_settings") or {}).get("reasoning_effort")
                                         for s in samples if s["log"].get("llm_called"))),
        "output_tokens_per_call": (f"{statistics.mean(o):.0f}" if (o := [l["output_tokens"] for l in logs if l.get("output_tokens")]) else "n/a"),
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for name in sys.argv[1:]:
        print(f"\n== {name}")
        for key, value in summarize(Path(name)).items():
            print(f"  {key:32} {value}")


if __name__ == "__main__":
    main()
