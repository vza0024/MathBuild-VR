"""Automatic quality check of real tutor replies. No API calls.

Reads one or more samples.jsonl files (from run_samples.py or the benchmark) and
checks every reply the child would hear:

  answer_leak      the hidden answer appears (digit or word) where it is not a
                   quantity the story states or a count the learner can see
  exact_move       tells the learner exactly how many objects to move
  too_long         more than 45 words
  asks_to_place_present   tells the learner to place or add a part that is already
                   complete (e.g. "place seven red apples" when they are there)
  asks_to_create_existing tells the learner to make a group or collection that
                   already exists (ratio collections, sharing recipients, or
                   groups when there are already enough)
  claims_missing   says a part is missing / empty / not there when it has objects
  claims_too_many  says something has too many when the evaluator found no error

The grounding checks (the last four) are pattern rules: they catch the mistakes
seen so far and similar ones, but a flagged reply should still be read by hand,
and an unflagged one is not proof of a perfect reply.

    python scripts/check_replies.py samples/step1/run-*/samples.jsonl
    python scripts/check_replies.py samples/benchmark/<time>/*/tutor/samples.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from app.answer_protection import number_values  # noqa: E402
from app.evaluator import hidden_answer  # noqa: E402
from app.fallback import states_exact_move  # noqa: E402
from app.questions import QUESTION_BY_ID, student_safe  # noqa: E402

MAX_WORDS = 45
_PLACE = r"\b(?:start by\s+)?(?:plac(?:e|ing)|put(?:ting)?|add(?:ing)?|mov(?:e|ing))\b"
_CREATE = r"\b(?:mak(?:e|ing)|creat(?:e|ing)|build(?:ing)?|add(?:ing)?)\s+(?:a|another|the|new|one)?\s*(?:new\s+)?(?:group|collection|area|basket|pile)s?\b"
_MISSING = r"\b(?:missing|empty|no\s+\w+\s+yet|not\s+there|aren[’']?t\s+any|isn[’']?t\s+any|none\s+yet|haven[’']?t\s+(?:been\s+)?(?:placed|added))\b"
_TOO_MANY = r"\b(?:too many|more\s+\w*\s*than the story|more than (?:a fair share|the story))\b"


def _label(visual: dict, *keys: str) -> list[str]:
    return [str(visual[k]).lower() for k in keys if visual.get(k)]


def _mentions(text: str, labels: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(l.rstrip('s'))}s?\b", text) for l in labels)


def check_reply(question: dict[str, Any], state: dict[str, Any], log: dict[str, Any]) -> list[str]:
    """Return the problems found in one reply (empty list = none found)."""
    if log.get("status") == "confirmed_correct":
        return []
    text = (log.get("final_text") or "").strip()
    low = text.lower()
    flags: list[str] = []
    interaction = question["interaction"]
    visual = question.get("visual", {}) or {}
    p = question["parameters"]

    # --- answer leak -----------------------------------------------------------
    answer = hidden_answer(question)
    if answer >= 0 and answer in number_values(text):
        stated = {v for v in student_safe(question)["parameters"].values() if isinstance(v, int)}
        visible = {abs(v) for v in state.values() if isinstance(v, int) and not isinstance(v, bool)}
        visible |= {n for v in state.values() if isinstance(v, list) for n in v}
        visible |= {len(v) for v in state.values() if isinstance(v, list)}
        if answer not in stated | visible:
            flags.append("answer_leak")

    if states_exact_move(text):
        flags.append("exact_move")
    if len(text.split()) > MAX_WORDS:
        flags.append("too_long")

    # --- grounding --------------------------------------------------------------
    status = log.get("construction_status")
    if interaction == "JOIN":
        start_labels = _label(visual, "initial_object_label") or ["starting"]
        join_labels = _label(visual, "change_object_label")
        a = state.get("part_a_count")
        b = state.get("part_b_count")
        start_complete = (a == p["initial"]) if a is not None else (state.get("current_count", 0) >= p["initial"]
                                                                    and state.get("added_count", 0) >= 0)
        join_complete = b is not None and b >= p["change"]
        for sentence in re.split(r"[.!?]", low):
            if re.search(_PLACE, sentence):
                if start_complete and _mentions(sentence, start_labels) and not _mentions(sentence, join_labels):
                    flags.append("asks_to_place_present")
                if join_complete and join_labels and _mentions(sentence, join_labels) and not _mentions(sentence, start_labels):
                    flags.append("asks_to_place_present")
            if re.search(_MISSING, sentence):
                if a and _mentions(sentence, start_labels) and not _mentions(sentence, join_labels):
                    flags.append("claims_missing")
                if b and join_labels and _mentions(sentence, join_labels) and not _mentions(sentence, start_labels):
                    flags.append("claims_missing")
    elif interaction == "PART_TO_PART_RATIO":
        if re.search(_CREATE, low):
            flags.append("asks_to_create_existing")
    elif interaction == "EQUAL_SHARING":
        if re.search(_CREATE, low):
            flags.append("asks_to_create_existing")
    elif interaction == "EQUAL_GROUPS":
        if re.search(_CREATE, low) and len(state.get("group_sizes", [])) >= p["group_count"]:
            flags.append("asks_to_create_existing")
        if re.search(r"\b(?:aren[’']?t any|no)\s+(?:groups|cousins|\w+s)\s+(?:in your arrangement\s+)?yet\b", low) \
                and state.get("group_sizes"):
            flags.append("claims_missing")
    if status != "incorrect" and re.search(_TOO_MANY, low):
        flags.append("claims_too_many")
    return sorted(set(flags))


def check_file(path: Path) -> tuple[int, Counter, list[dict]]:
    samples = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts, flagged, checked = Counter(), [], 0
    for sample in samples:
        log = sample["log"]
        if log.get("status") == "confirmed_correct":
            continue
        checked += 1
        question = QUESTION_BY_ID[sample["question_id"]]
        found = check_reply(question, sample["request"]["learner_state"], log)
        for f in found:
            counts[f] += 1
        if found:
            flagged.append({"flags": found, "interaction": question["interaction"],
                            "state": sample.get("state_label"), "support_type": sample["request"]["support_type"],
                            "reply": log.get("final_text")})
    return checked, counts, flagged


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for name in sys.argv[1:]:
        checked, counts, flagged = check_file(Path(name))
        clean = checked - len(flagged)
        print(f"\n== {name}\n  replies checked: {checked}   no problem found: {clean}   flagged: {len(flagged)}")
        for flag, n in counts.most_common():
            print(f"    {flag:26} {n}")
        for row in flagged:
            print(f"  - [{', '.join(row['flags'])}] {row['interaction']} {row['state']} {row['support_type']}: "
                  f"{row['reply']}")


if __name__ == "__main__":
    main()
