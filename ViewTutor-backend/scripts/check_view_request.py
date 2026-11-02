"""Check captured Unity /api/tutor request bodies against the backend's POV rules.

No API calls, no server needed. For each request it reports which `view.regions`
the backend recognizes, which it drops, what visibility class each gets, and
whether the snapshot fields are present.

    python scripts/check_view_request.py captures/join_two_columns.json captures/*.json

Each file is one request body (JSON object), or a JSONL file with one per line.
Safe to share the output; it prints no learner text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pov_context import build_pov_context  # noqa: E402
from app.questions import load_questions  # noqa: E402
from app.schemas import ViewData  # noqa: E402


def load_bodies(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def check(body: dict, questions: dict[str, dict]) -> list[str]:
    lines: list[str] = []
    qid = body.get("question_id")
    question = questions.get(qid)
    if question is None:
        return [f"  question_id {qid!r} not found in data/questions.json"]
    lines.append(f"  question_id: {qid}  ({question['interaction']})")
    raw_view = body.get("view")
    if not raw_view:
        return lines + ["  PROBLEM: no `view` object in this request"]
    try:
        view = ViewData.model_validate(raw_view)
    except Exception as exc:  # noqa: BLE001 - report any schema problem
        return lines + [f"  PROBLEM: `view` does not validate: {exc}"]
    for field in ("snapshot_source", "snapshot_age_ms", "attempt_id"):
        value = getattr(view, field)
        lines.append(f"  {field}: {value!r}" + ("" if value is not None else "   <-- missing"))
    sent = [r.region_id for r in (view.regions or [])]
    lines.append(f"  region IDs sent: {sent}")
    context, warnings = build_pov_context(question, view, learner_state=body.get("learner_state"))
    used = context["regions"] if context else []
    for region in used:
        lines.append(f"  OK   {region['region_name']!r:34} {region['visibility']}")
    for warning in warnings:
        lines.append(f"  DROPPED  {warning}")
    if not used:
        lines.append("  PROBLEM: no usable regions for the tutor")
    return lines


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    questions = {q["id"]: q for q in load_questions()}
    problems = 0
    for name in argv:
        path = Path(name)
        print(f"\n{path.name}")
        for i, body in enumerate(load_bodies(path), 1):
            if i > 1:
                print(f"  --- request {i}")
            out = check(body, questions)
            problems += sum(("PROBLEM" in line or "DROPPED" in line) for line in out)
            print("\n".join(out))
    print(f"\n{problems} problem/dropped-region line(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
