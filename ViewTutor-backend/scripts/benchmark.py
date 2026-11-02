"""Run the tutor samples (and optionally the correctness check) for several settings.

Each setting is "model:effort" or "model:effort:prompt" (prompt = step1-v2, the default, or step1-v1).
Runs one after another and prints a comparison table.

    python scripts/benchmark.py --settings gpt-6.1-sol:low gpt-6.1-sol:medium gpt-6-luna:none gpt-6-luna:low
    python scripts/benchmark.py --settings gpt-6.1-sol:low gpt-6-luna:none --correctness

Use --per-type 1 for a cheap first pass (about 84 LLM calls per setting for the tutor
samples, 22 for the correctness check). Output folders: samples/benchmark/<time>/<setting>/.
A setting the account or model does not support shows up as api_error, not as a crash.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.compare_runs import summarize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", nargs="+", required=True, help="model:effort, e.g. gpt-6.1-sol:low")
    parser.add_argument("--per-type", type=int, default=1)
    parser.add_argument("--correctness", action="store_true", help="also run the LLM correctness check")
    parser.add_argument("--prices", type=Path, default=PROJECT / "prices.example.json")
    args = parser.parse_args()

    root = PROJECT / "samples" / "benchmark" / f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    rows = []
    judged = set()          # correctness test runs once per model:effort (it does not use the tutor prompt)
    for setting in args.settings:
        model, _, rest = setting.partition(":")
        effort, _, prompt = rest.partition(":")
        effort = effort or "off"
        prompt = prompt or "step1-v2"
        folder = root / f"{model}_{effort}_{prompt.replace('step1-', '')}"
        print(f"\n=== {model}  reasoning={effort}  prompt={prompt}")
        cmd = [sys.executable, str(PROJECT / "scripts" / "run_samples.py"), "--per-type", str(args.per_type),
               "--model", model, "--reasoning", effort, "--prompt", prompt, "--out", str(folder / "tutor")]
        if args.prices.exists():
            cmd += ["--prices", str(args.prices)]
        subprocess.run(cmd, check=False, env={**__import__("os").environ, "USE_MOCK_LLM": "0"})
        row = {"setting": f"{model}:{effort}:{prompt}"}
        samples = folder / "tutor" / "samples.jsonl"
        if samples.exists():
            s = summarize(samples)
            row.update({"latency": s["api_latency_ms"], "blocked": s["block_rate"],
                        "exact_moves": s["exact_move_in_generated"], "out_tokens": s["output_tokens_per_call"],
                        "statuses": s["statuses"]})
        if samples.exists():
            from scripts.check_replies import check_file
            checked, counts, flagged = check_file(samples)
            row["reply_problems"] = f"{len(flagged)}/{checked}" + (f" {dict(counts)}" if counts else "")
        if args.correctness and (model, effort) not in judged:
            judged.add((model, effort))
            subprocess.run([sys.executable, str(PROJECT / "scripts" / "llm_correctness_check.py"),
                            "--per-type", str(args.per_type), "--model", model, "--reasoning", effort,
                            "--out", str(folder / "correctness")], check=False)
            summary = folder / "correctness" / "summary.json"
            if summary.exists():
                c = json.loads(summary.read_text())
                row.update({"llm_correctness": c["accuracy"], "false_correct": c["false_correct"]})
        rows.append(row)

    (root / "benchmark.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("\n=== Comparison")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    print(f"\nsaved: {root / 'benchmark.json'}")
    print("\n=== Side-by-side review")
    subprocess.run([sys.executable, str(PROJECT / "scripts" / "review_benchmark.py"), str(root)], check=False)


if __name__ == "__main__":
    main()
