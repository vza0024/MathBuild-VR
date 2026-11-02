"""Scripted learner states for the sample run (plan steps 14 and 16).

Each state is labelled with the construction status it must produce and is
physically consistent with the Unity workspace: totals that Unity keeps fixed
(REMOVE, EQUAL_SHARING, RATIO; see validation.conservation_warnings) add up, and
JOIN `added_count` follows Unity's rule (current minus the starting amount in the
totals mode, clamped at 0 in two-part modes). `tests/unit/test_sample_states.py`
checks every state against the validator and the evaluator.
"""
from __future__ import annotations

from typing import Any, Mapping

SampleState = tuple[str, str, dict[str, Any]]   # (label, expected construction status, learner state)


def _join(p: Mapping[str, int]) -> list[SampleState]:
    initial, change, result = p["initial"], p["change"], p["result"]
    def two_parts(a: int, b: int) -> dict[str, Any]:
        return {"added_count": max(0, a + b - initial), "current_count": a + b, "part_a_count": a,
                "part_b_count": b, "total_count": a + b, "workspace_mode": "single_destination_two_sources"}
    return [
        ("totals_incomplete", "incomplete", {"added_count": 0, "current_count": initial}),
        ("totals_correct", "correct", {"added_count": change, "current_count": result}),
        ("totals_one_extra", "incorrect", {"added_count": change + 1, "current_count": result + 1}),
        ("totals_starting_object_moved_out", "incomplete", {"added_count": -1, "current_count": initial - 1}),
        ("parts_incomplete", "incomplete", two_parts(initial, 0)),
        ("parts_correct", "correct", two_parts(initial, change)),
        ("parts_error_while_unfinished", "incorrect", two_parts(0, change + 1)),
        ("parts_two_errors", "incorrect", two_parts(initial + 1, change + 1)),
    ]


def _remove(p: Mapping[str, int]) -> list[SampleState]:
    initial, change, result = p["initial"], p["change"], p["result"]
    states = [
        ("nothing_removed", "incomplete", {"removed_count": 0, "remaining_count": initial}),
        ("correct", "correct", {"removed_count": change, "remaining_count": result}),
    ]
    if change >= 2:
        states.append(("partly_removed", "incomplete", {"removed_count": change - 1, "remaining_count": result + 1}))
    if result >= 1:
        states.append(("one_too_many_removed", "incorrect", {"removed_count": change + 1, "remaining_count": result - 1}))
    return states


def _groups(p: Mapping[str, int]) -> list[SampleState]:
    # The printer tray adds objects, so groups + tray need not equal the story total.
    count, size = p["group_count"], p["group_size"]
    full = [size] * count
    states = [
        ("no_groups", "incomplete", {"group_sizes": [], "undistributed_count": 0}),
        ("one_group_done", "incomplete", {"group_sizes": [size], "undistributed_count": 0}),
        ("correct", "correct", {"group_sizes": full, "undistributed_count": 0}),
        ("objects_left_in_tray", "incomplete", {"group_sizes": full, "undistributed_count": 1}),
        ("one_group_too_big", "incorrect", {"group_sizes": [size + 1], "undistributed_count": 0}),
        ("extra_group", "incorrect", {"group_sizes": full + [size], "undistributed_count": 0}),
        ("two_errors", "incorrect", {"group_sizes": [size + 1] + full, "undistributed_count": 0}),
    ]
    return states


def _sharing(p: Mapping[str, int]) -> list[SampleState]:
    total, n, share = p["total"], p["recipient_count"], p["share_size"]
    states = [
        ("nothing_shared", "incomplete", {"share_sizes": [0] * n, "undistributed_count": total}),
        ("dealing_out", "incomplete", {"share_sizes": [1] + [0] * (n - 1), "undistributed_count": total - 1}),
        ("correct", "correct", {"share_sizes": [share] * n, "undistributed_count": 0}),
    ]
    if n >= 2:
        over = [share + 1, share - 1] + [share] * (n - 2)
        states.append(("one_share_too_big", "incorrect", {"share_sizes": over, "undistributed_count": 0}))
    if n >= 3 and share >= 1:
        two = [share + 1, share + 1, share - 2] + [share] * (n - 3) if share >= 2 else None
        if two:
            states.append(("two_shares_too_big", "incorrect", {"share_sizes": two, "undistributed_count": 0}))
    return states


def _ratio(p: Mapping[str, int]) -> list[SampleState]:
    a, b = p["part_a"], p["part_b"]
    return [
        ("nothing_placed", "incomplete", {"part_a_count": 0, "part_b_count": 0, "unassigned_a": a, "unassigned_b": b}),
        ("first_part_done", "incomplete", {"part_a_count": a, "part_b_count": 0, "unassigned_a": 0, "unassigned_b": b}),
        ("correct", "correct", {"part_a_count": a, "part_b_count": b, "unassigned_a": 0, "unassigned_b": 0}),
    ]
    # RATIO cannot hold "too many" without breaking the fixed totals Unity keeps,
    # so no incorrect state is scripted for it.


_BUILDERS = {"JOIN": _join, "REMOVE": _remove, "EQUAL_GROUPS": _groups,
             "EQUAL_SHARING": _sharing, "PART_TO_PART_RATIO": _ratio}


def sample_states(question: Mapping[str, Any]) -> list[SampleState]:
    states = _BUILDERS[question["interaction"]](question["parameters"])
    return [(label, status, {**state, "answer": None}) for label, status, state in states]
