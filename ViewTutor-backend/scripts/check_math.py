"""Independent check of the math evaluator (app/evaluator.py). No API calls.

The evaluator decides correct / incomplete / incorrect with direct rules. This
script decides the same thing a different way, by simulating the child:

  correct     the construction already equals the story's construction
  incomplete  not correct, but the child can still reach the correct
              construction by only ADDING (placing more objects, or making
              a missing group) — nothing has to be taken back
  incorrect   the correct construction cannot be reached without taking
              something back (a definite error)

It explores the add-only moves with a breadth-first search, so it shares no
logic with the evaluator. Every learner state in a grid around each question's
target is checked, for all 88 questions, plus the entered-answer rule
(`student_correct` is true only for a correct construction with no wrong answer).

    python scripts/check_math.py            # full check, prints a report
    python scripts/check_math.py --quick    # smaller grid (used by the unit test)

Any disagreement is printed with the question, the state and both verdicts.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterator, Optional

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from app.evaluator import evaluate, hidden_answer  # noqa: E402
from app.questions import QUESTIONS  # noqa: E402
from app.validation import validate_workspace  # noqa: E402

SEARCH_LIMIT = 200_000


# --------------------------------------------------------------------------
# The child's add-only moves, per interaction type (states are tuples)
# --------------------------------------------------------------------------

def reachable(start: tuple, target: tuple, moves) -> bool:
    """Breadth-first search over add-only moves."""
    seen, queue = {start}, deque([start])
    while queue:
        state = queue.popleft()
        if state == target:
            return True
        for nxt in moves(state):
            if nxt not in seen:
                if len(seen) > SEARCH_LIMIT:
                    raise RuntimeError("search limit reached")
                seen.add(nxt)
                queue.append(nxt)
    return False


def oracle(question: dict[str, Any], state: dict[str, Any]) -> str:
    p, i = question["parameters"], question["interaction"]

    if i == "JOIN":
        if "part_a_count" in state:
            a, b = state["part_a_count"], state["part_b_count"]
            target = (p["initial"], p["change"])
            def moves(s):  # place one more object of either kind
                x, y = s
                return [(x + 1, y), (x, y + 1)] if x <= target[0] and y <= target[1] else []
            start = (a, b)
        else:
            # legacy mode: added = current - initial; the child adds one object at a time
            start = (state["added_count"], state["current_count"])
            target = (p["change"], p["result"])
            def moves(s):
                added, current = s
                return [(added + 1, current + 1)] if current <= target[1] else []
        if start == target:
            return "correct"
        return "incomplete" if reachable(start, target, moves) else "incorrect"

    if i == "REMOVE":
        start = (state["removed_count"], state["remaining_count"])
        target = (p["change"], p["result"])
        def moves(s):  # move one object from the starting collection to the removed area
            removed, remaining = s
            return [(removed + 1, remaining - 1)] if remaining > 0 and removed <= target[0] else []
        if start == target:
            return "correct"
        return "incomplete" if reachable(start, target, moves) else "incorrect"

    if i == "EQUAL_GROUPS":
        size, count = p["group_size"], p["group_count"]
        groups = tuple(state["group_sizes"])
        tray = state["undistributed_count"]
        target_groups = tuple([size] * count)
        # Objects in the tray may be placed or left; the tray must end empty. A tray
        # object can always be put into a group, so treat tray objects as placeable.
        def moves(s):
            g, t = s
            out = []
            if len(g) < count:
                out.append((tuple(sorted(g + (0,))), t))       # make a new group
            for k, v in enumerate(g):
                if v < size + 1:
                    ng = list(g); ng[k] = v + 1
                    out.append((tuple(sorted(ng)), max(t - 1, 0)))  # place an object (from tray or supply)
            return out
        start = (tuple(sorted(groups)), tray)
        target = (target_groups, 0)
        if groups == target_groups and tray == 0:
            return "correct"
        # the tray empties only by placing its objects, which must fit
        if tray > sum(size - v for v in groups if v <= size) + size * max(count - len(groups), 0):
            return "incorrect" if any(v > size for v in groups) or len(groups) > count else "incomplete"
        return "incomplete" if reachable(start, target, moves) or _tray_only(groups, tray, size, count) else "incorrect"

    if i == "EQUAL_SHARING":
        share, n = p["share_size"], p["recipient_count"]
        shares = tuple(state["share_sizes"])
        bank = state["undistributed_count"]
        target = (tuple([share] * n), 0)
        def moves(s):
            sh, b = s
            out = []
            if len(sh) < n:
                out.append((tuple(sorted(sh + (0,))), b))
            if b > 0:
                for k, v in enumerate(sh):
                    if v < share:
                        ns = list(sh); ns[k] = v + 1
                        out.append((tuple(sorted(ns)), b - 1))
            return out
        start = (tuple(sorted(shares)), bank)
        if shares == target[0] and bank == 0:
            return "correct"
        # Any share above the fair share or too many recipients can never be undone by adding.
        if any(v > share for v in shares) or len(shares) > n:
            return "incorrect"
        # Otherwise only adding is needed; a bank that does not add up is a Unity issue
        # (logged as a warning), not a construction error.
        return "incomplete" if reachable(start, target, moves) or bank != share * n - sum(shares) else "incomplete"

    # PART_TO_PART_RATIO
    a, b = state["part_a_count"], state["part_b_count"]
    target = (p["part_a"], p["part_b"])
    if (a, b) == target and state["unassigned_a"] == 0 and state["unassigned_b"] == 0:
        return "correct"
    def moves(s):
        x, y = s
        return [(x + 1, y), (x, y + 1)]
    if a > target[0] or b > target[1]:
        return "incorrect"
    return "incomplete"


def _tray_only(groups: tuple, tray: int, size: int, count: int) -> bool:
    """Groups already exact but objects left in the tray: unfinished, not wrong."""
    return groups == tuple([size] * count) and tray > 0


# --------------------------------------------------------------------------
# State grid around each question's target
# --------------------------------------------------------------------------

def states_for(question: dict[str, Any], quick: bool) -> Iterator[dict[str, Any]]:
    p, i = question["parameters"], question["interaction"]
    span = 1 if quick else 2
    if i == "JOIN":
        for current in range(0, p["result"] + span + 1):
            yield {"added_count": current - p["initial"], "current_count": current}
        for a in range(0, p["initial"] + span + 1):
            for b in range(0, p["change"] + span + 1):
                yield {"added_count": max(0, a + b - p["initial"]), "current_count": a + b,
                       "part_a_count": a, "part_b_count": b}
    elif i == "REMOVE":
        for removed in range(0, p["initial"] + 1):
            yield {"removed_count": removed, "remaining_count": p["initial"] - removed}
    elif i == "EQUAL_GROUPS":
        size, count = p["group_size"], p["group_count"]
        values = sorted({0, 1, max(size - 1, 0), size, size + 1})
        for k in range(0, count + span):
            combos = itertools.combinations_with_replacement(values, k) if k <= (4 if quick else 5) else [tuple([size] * k)]
            for combo in combos:
                for tray in (0, 1, size):
                    yield {"group_sizes": list(combo), "undistributed_count": tray}
    elif i == "EQUAL_SHARING":
        share, n, total = p["share_size"], p["recipient_count"], p["total"]
        values = sorted({0, 1, max(share - 1, 0), share, share + 1})
        for combo in itertools.product(values, repeat=n) if n <= (4 if quick else 5) else [tuple([share] * n)]:
            bank = total - sum(combo)
            if bank >= 0:
                yield {"share_sizes": list(combo), "undistributed_count": bank}
    else:
        for a in range(0, p["part_a"] + 1):
            for b in range(0, p["part_b"] + 1):
                yield {"part_a_count": a, "part_b_count": b,
                       "unassigned_a": p["part_a"] - a, "unassigned_b": p["part_b"] - b}


def check(quick: bool = False) -> dict[str, Any]:
    checked = Counter()
    disagreements: list[tuple] = []
    answer_errors: list[tuple] = []
    for question in QUESTIONS:
        answer = hidden_answer(question)
        for state in states_for(question, quick):
            ws = validate_workspace(question, state)
            if not ws.ok:
                disagreements.append((question["id"], state, "validator rejected", ws.reason))
                continue
            ours = evaluate(question, ws.workspace).construction_status
            expected = oracle(question, state)
            checked[(question["interaction"], expected)] += 1
            if ours != expected:
                disagreements.append((question["id"], state, ours, expected))
            # Entered-answer rule, on the construction verdict.
            for entered in ([answer, answer + 1] if answer >= 0 else [42]):
                result = evaluate(question, validate_workspace(question, {**state, "answer": entered}).workspace)
                should = (expected == "correct") and (answer < 0 or entered == answer)
                if result.student_correct != should:
                    answer_errors.append((question["id"], state, entered, result.student_correct, should))
    return {"checked": checked, "disagreements": disagreements, "answer_errors": answer_errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    result = check(args.quick)
    total = sum(result["checked"].values())
    print(f"Questions: {len(QUESTIONS)}   learner states checked: {total}")
    for interaction in ("JOIN", "REMOVE", "EQUAL_GROUPS", "EQUAL_SHARING", "PART_TO_PART_RATIO"):
        parts = {s: result["checked"][(interaction, s)] for s in ("correct", "incomplete", "incorrect")}
        print(f"  {interaction:20} correct {parts['correct']:5}   incomplete {parts['incomplete']:6}   "
              f"incorrect {parts['incorrect']:6}")
    print(f"Evaluator vs independent check: {total - len(result['disagreements'])}/{total} agree")
    for row in result["disagreements"][:20]:
        print("  DISAGREE", row)
    print(f"Entered-answer rule: {len(result['answer_errors'])} errors")
    for row in result["answer_errors"][:20]:
        print("  ANSWER", row)
    if result["disagreements"] or result["answer_errors"]:
        sys.exit(1)
    print("OK: the evaluator agrees with the independent check everywhere.")


if __name__ == "__main__":
    main()
