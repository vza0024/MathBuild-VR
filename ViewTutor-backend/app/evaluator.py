"""Deterministic evaluation of the learner's construction. No LLM involved.

Ported from v4 `evaluator.evaluate` and extended with a three-way construction
status, checked in this priority order:

1. ``incorrect`` — a definite construction error exists, even if unfinished
   (e.g. a group already holds more than the story says).
2. ``correct``   — finished and matches the story.
3. ``incomplete`` — anything else: unfinished, with no definite error yet.

The entered answer is checked separately (v4 rules). ``student_correct`` is
True only when the construction is correct and the entered answer, if any, is
correct.

The returned ``facts`` dict keeps every key v4 produced, so the ported
answer-protection and next-step code can use it unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional

from app.validation import Workspace

ConstructionStatus = Literal["correct", "incomplete", "incorrect"]


@dataclass(frozen=True)
class Evaluation:
    """Everything the rest of the pipeline and the research log need."""

    construction_status: ConstructionStatus
    # Concrete error descriptions for the prompt and log. They contain only the
    # learner's own counts and quantities the story states openly, never a value
    # the learner must find (tested against the hidden answer of every question).
    errors: tuple[str, ...]
    answer_entered: bool
    answer_parseable: bool
    answer_correct: Optional[bool]     # None when no answer was entered
    student_correct: bool
    facts: Mapping[str, Any] = field(default_factory=dict)  # v4-compatible facts
    # Verified observations that are not errors (the work can still be fixed by
    # adding), e.g. starting objects moved out of a JOIN collection.
    notes: tuple[str, ...] = ()

    @property
    def conversation_status(self) -> str:
        return "correct" if self.student_correct else "continue"


def hidden_answer(question: Mapping[str, Any]) -> int:
    """The number the learner must find (v4 `hidden_answer`). -1 for ratio."""
    params = question["parameters"]
    interaction = question["interaction"]
    if interaction in {"JOIN", "REMOVE"}:
        return int(params["change"] if question.get("unknown_position") == "CHANGE" else params["result"])
    if interaction == "EQUAL_GROUPS":
        return int(params["total"])
    if interaction == "EQUAL_SHARING":
        return int(params["share_size"])
    return -1  # ratio representation: both parts are stated, nothing numeric is hidden


def _status(errors: list[str], finished_and_matching: bool) -> ConstructionStatus:
    if errors:
        return "incorrect"
    return "correct" if finished_and_matching else "incomplete"


# --------------------------------------------------------------------------
# Per interaction type
# --------------------------------------------------------------------------

def _join(question: Mapping[str, Any], ws: Workspace) -> tuple[ConstructionStatus, list[str], dict[str, Any]]:
    p = question["parameters"]
    v = ws.values
    initial, change, result = p["initial"], p["change"], p["result"]
    added, current = v["added_count"], v["current_count"]
    part_a, part_b = v.get("part_a_count"), v.get("part_b_count")
    errors: list[str] = []
    notes: list[str] = []

    if part_a is not None and part_b is not None:
        # Two-part modes: part A is the starting quantity, part B the joining one.
        # Judged on the parts, because Unity clamps added_count at 0 in these modes
        # and a wrong split (e.g. 0 red + 7 green) would be invisible otherwise.
        mode = "two_parts"
        if part_a > initial:
            errors.append(f"part A has {part_a}, story states {initial}")
        if part_b > change:
            errors.append(f"part B has {part_b}, more than the story's joining amount")
        matching = part_a == initial and part_b == change
    else:
        # One-destination or legacy mode: judged on the totals, as in v4.
        mode = "totals"
        if current > result:
            errors.append(f"collection has {current}, more than the story ends with")
        if added < 0:
            # Not a definite error: putting the objects back (adding) fixes it.
            notes.append(f"{-added} starting objects were moved out of the collection")
        matching = added == change and current == result

    status = _status(errors, matching)
    unknown = question.get("unknown_position")
    facts = {
        "interaction": "JOIN",
        "unknown_position": unknown,
        "expected_initial_count": initial,
        "expected_added_count": change,
        "expected_final_count": result,
        "learner_added_count": added,
        "learner_final_count": current,
        "join_mode": mode,
        "learner_part_a_count": part_a,
        "learner_part_b_count": part_b,
        "expected_answer": change if unknown == "CHANGE" else result,
        "work_answer": added if unknown == "CHANGE" else current,
        "work_correct": status == "correct",
        "evaluator_notes": notes,
    }
    return status, errors, facts


def _remove(question: Mapping[str, Any], ws: Workspace) -> tuple[ConstructionStatus, list[str], dict[str, Any]]:
    p = question["parameters"]
    v = ws.values
    initial, change, result = p["initial"], p["change"], p["result"]
    removed, remaining = v["removed_count"], v["remaining_count"]
    errors: list[str] = []
    if removed > change:
        errors.append(f"removed area has {removed}, more than the story removes")
    if remaining < result:
        errors.append(f"remaining collection has {remaining}, fewer than the story leaves")
    status = _status(errors, removed == change and remaining == result)
    unknown = question.get("unknown_position")
    facts = {
        "interaction": "REMOVE",
        "unknown_position": unknown,
        "expected_initial_count": initial,
        "expected_removed_count": change,
        "expected_remaining_count": result,
        "learner_removed_count": removed,
        "learner_remaining_count": remaining,
        "expected_answer": change if unknown == "CHANGE" else result,
        "work_answer": removed if unknown == "CHANGE" else remaining,
        "work_correct": status == "correct",
    }
    return status, errors, facts


def _equal_groups(question: Mapping[str, Any], ws: Workspace) -> tuple[ConstructionStatus, list[str], dict[str, Any]]:
    p = question["parameters"]
    count, size, total = p["group_count"], p["group_size"], p["total"]
    sizes = list(ws.values["group_sizes"])
    undistributed = ws.values["undistributed_count"]
    errors: list[str] = []
    if len(sizes) > count:
        errors.append(f"{len(sizes)} groups built, story has {count}")
    for index, value in enumerate(sizes, start=1):
        if value > size:
            errors.append(f"group {index} has {value}, story puts {size} in each")
    matching = sizes == [size] * count and undistributed == 0
    status = _status(errors, matching)
    facts = {
        "interaction": "EQUAL_GROUPS",
        "expected_group_count": count,
        "expected_group_size": size,
        "expected_total": total,
        "learner_group_count": len(sizes),
        "learner_group_sizes": sizes,
        "learner_total": sum(sizes),
        "undistributed_count": undistributed,
        "expected_answer": total,
        "work_answer": sum(sizes),
        "groups_are_equal": bool(sizes) and len(set(sizes)) == 1,
        "work_correct": status == "correct",
    }
    return status, errors, facts


def _equal_sharing(question: Mapping[str, Any], ws: Workspace) -> tuple[ConstructionStatus, list[str], dict[str, Any]]:
    p = question["parameters"]
    recipients, share, total = p["recipient_count"], p["share_size"], p["total"]
    sizes = list(ws.values["share_sizes"])
    undistributed = ws.values["undistributed_count"]
    errors: list[str] = []
    if len(sizes) > recipients:
        errors.append(f"{len(sizes)} recipients, story has {recipients}")
    for index, value in enumerate(sizes, start=1):
        if value > share:
            errors.append(f"recipient {index} has more than a fair share")
    matching = sizes == [share] * recipients and undistributed == 0
    status = _status(errors, matching)
    facts = {
        "interaction": "EQUAL_SHARING",
        "expected_recipient_count": recipients,
        "expected_share_size": share,
        "expected_total": total,
        "learner_recipient_count": len(sizes),
        "learner_share_sizes": sizes,
        "undistributed_count": undistributed,
        "total_distributed": sum(sizes),
        "expected_answer": share,
        "work_answer": sizes[0] if sizes and len(set(sizes)) == 1 else None,
        "shares_are_equal": bool(sizes) and len(set(sizes)) == 1,
        "work_correct": status == "correct",
    }
    return status, errors, facts


def _ratio(question: Mapping[str, Any], ws: Workspace) -> tuple[ConstructionStatus, list[str], dict[str, Any]]:
    p = question["parameters"]
    v = ws.values
    target_a, target_b = p["part_a"], p["part_b"]
    a, b = v["part_a_count"], v["part_b_count"]
    errors: list[str] = []
    if a > target_a:
        errors.append(f"first collection has {a}, story states {target_a}")
    if b > target_b:
        errors.append(f"second collection has {b}, story states {target_b}")
    matching = a == target_a and b == target_b and v["unassigned_a"] == 0 and v["unassigned_b"] == 0
    status = _status(errors, matching)
    facts = {
        "interaction": "PART_TO_PART_RATIO",
        "expected_part_a": target_a,
        "expected_part_b": target_b,
        "learner_part_a": a,
        "learner_part_b": b,
        "unassigned_a": v["unassigned_a"],
        "unassigned_b": v["unassigned_b"],
        "expected_answer": None,
        "work_answer": f"{a}:{b}",
        "ratio_order_correct": a == target_a and b == target_b,
        "work_correct": status == "correct",
    }
    return status, errors, facts


_EVALUATORS = {
    "JOIN": _join,
    "REMOVE": _remove,
    "EQUAL_GROUPS": _equal_groups,
    "EQUAL_SHARING": _equal_sharing,
    "PART_TO_PART_RATIO": _ratio,
}


def evaluate(question: Mapping[str, Any], workspace: Workspace) -> Evaluation:
    """Evaluate a validated workspace against its question."""
    status, errors, facts = _EVALUATORS[question["interaction"]](question, workspace)

    # Entered answer (v4 rules). Ratio has no numeric answer: any parseable entry passes.
    answer = workspace.answer
    answer_entered = answer is not None or workspace.answer_invalid
    answer_parseable = answer_entered and not workspace.answer_invalid
    if not answer_entered:
        answer_correct: Optional[bool] = None
        supported = True
    elif not answer_parseable:
        answer_correct, supported = False, False
    elif question["interaction"] == "PART_TO_PART_RATIO":
        answer_correct, supported = True, True
    else:
        answer_correct = answer == facts["expected_answer"]
        supported = answer == facts["work_answer"]

    student_correct = status == "correct" and answer_correct is not False

    facts.update({
        "construction_status": status,
        "entered_answer": answer if answer_parseable else None,
        "answer_entered": answer_entered,
        "answer_parseable": answer_parseable,
        "answer_supported_by_work": supported,
        "answer_correct_if_entered": answer_correct is not False,
        "student_correct": student_correct,
    })
    return Evaluation(
        construction_status=status,
        errors=tuple(errors),
        answer_entered=answer_entered,
        answer_parseable=answer_parseable,
        answer_correct=answer_correct,
        student_correct=student_correct,
        facts=facts,
        notes=tuple(facts.pop("evaluator_notes", ())),
    )
