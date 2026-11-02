"""Deterministic teaching facts: stated quantities, the next safe step, fallback texts.

Ported from v4 `strategies.py`. Changes from v4 are marked "Change from v4" and
listed in the README. Nothing here calls the LLM.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from app.evaluator import hidden_answer
from app.schemas import SupportType

SUPPORT_OPTIONS: dict[str, dict[str, str]] = {
    "SIMPLIFY_STORY": {
        "label": "What is the story asking me?",
        "goal": "Help the learner identify what the story is asking and connect the important story quantities without solving the problem.",
    },
    "CHECK_WORK": {
        "label": "Can you check what I did?",
        "goal": "Review the learner's current arrangement, identify one important feature to inspect, and invite the learner to compare the work with the story without giving the answer.",
    },
    "HINT": {
        "label": "Can I get a hint?",
        "goal": "Give exactly one small, useful hint based on the current arrangement without giving the answer or completing the task for the learner.",
    },
    "OPEN_ENDED": {
        "label": "Learner's own message",
        "goal": "Respond directly to the learner's own question or explanation, independently infer what support is needed, and keep the response grounded in the current verified work without revealing the answer.",
    },
    "UNSURE": {
        "label": "I am not sure why this is wrong",
        "goal": "Acknowledge the learner's uncertainty and help them inspect one relevant part of the work without giving the answer.",
    },
    "INTERFACE_HELP": {
        "label": "Interface help",
        "goal": "Explain only the relevant screen control or how to move an object, without any counted mathematical correction.",
    },
    "AUTO_CHECK": {
        "label": "Automatic check",
        "goal": "Briefly describe the most important current mismatch and suggest one next action.",
    },
    # Change from v4: v4 accepted SMALLER_EXAMPLE but had no entry here, so every
    # such request raised KeyError (HTTP 503).
    "SMALLER_EXAMPLE": {
        "label": "Show me a smaller example",
        "goal": "Offer one smaller example with the same structure, using only the two example inputs, without solving it or the original problem.",
    },
}


def object_phrase(question: dict[str, Any], count: int = 2) -> str:
    visual = question.get("visual", {})
    return visual.get("object_label", "object") if count == 1 else visual.get("object_plural", "objects")


def region_name(question: dict[str, Any], kind: str, index: int) -> str:
    """The title the child sees on a region (Unity `FormatRecipientTitle` /
    `FormatGroupTitle`: "{Label} {number}"), or the story's own name when the
    question lists one (e.g. Jane, Mother, Father).

    Change from v4: v4 said "recipient 1" / "group 1", which is internal
    terminology.
    """
    visual = question.get("visual", {}) or {}
    if kind == "recipient":
        names = visual.get("recipient_labels") or []
        if index < len(names) and names[index]:
            return str(names[index])
        label = visual.get("recipient_label") or "recipient"
    else:
        label = visual.get("group_label") or "group"
    label = str(label).strip() or kind
    return f"{label[:1].upper()}{label[1:]} {index + 1}"


def safe_given_quantities(question: dict[str, Any]) -> dict[str, int]:
    """Return quantities stated in the story, excluding the unknown answer."""
    params = question["parameters"]
    interaction = question["interaction"]
    if interaction in {"JOIN", "REMOVE"}:
        if question.get("unknown_position") == "CHANGE":
            return {"starting quantity": int(params["initial"]), "ending quantity": int(params["result"])}
        return {"starting quantity": int(params["initial"]), "change quantity": int(params["change"])}
    if interaction == "EQUAL_GROUPS":
        return {"number of groups": int(params["group_count"]), "objects in each group": int(params["group_size"])}
    if interaction == "EQUAL_SHARING":
        return {"total objects": int(params["total"]), "number of recipients": int(params["recipient_count"])}
    return {"first part": int(params["part_a"]), "second part": int(params["part_b"])}


def _original_pair(question: dict[str, Any]) -> tuple[int, int]:
    params = question["parameters"]
    interaction = question["interaction"]
    if interaction in {"JOIN", "REMOVE"}:
        return int(params["initial"]), int(params["change"])
    if interaction == "EQUAL_GROUPS":
        return int(params["group_count"]), int(params["group_size"])
    if interaction == "EQUAL_SHARING":
        return int(params["total"]), int(params["recipient_count"])
    return int(params["part_a"]), int(params["part_b"])


def _example_result(interaction: str, first: int, second: int) -> int:
    if interaction == "JOIN":
        return first + second
    if interaction == "REMOVE":
        return first - second
    if interaction == "EQUAL_GROUPS":
        return first * second
    if interaction == "EQUAL_SHARING":
        return first // second
    return first + second


def _smaller_example(question: dict[str, Any]) -> dict[str, Any]:
    """Choose a genuinely different, usually smaller, structurally equivalent example.

    Only the input quantities are exposed to the tutor. The result remains hidden.
    """
    interaction = question["interaction"]
    original_first, original_second = _original_pair(question)
    params = question["parameters"]
    if interaction in {"JOIN", "REMOVE"}:
        original_scale = int(params["result"])
    elif interaction == "PART_TO_PART_RATIO":
        # Change from v4: ratio questions have no "total" (v4 raised KeyError).
        original_scale = int(params["part_a"]) + int(params["part_b"])
    else:
        original_scale = int(params["total"])
    answer = hidden_answer(question)

    candidates: dict[str, list[tuple[int, int]]] = {
        "JOIN": [(1, 1), (2, 1), (2, 2), (3, 1), (3, 2), (4, 1)],
        "REMOVE": [(2, 1), (3, 1), (3, 2), (4, 1), (4, 2), (5, 2)],
        "EQUAL_GROUPS": [(2, 1), (2, 2), (3, 1), (2, 3), (3, 2)],
        "EQUAL_SHARING": [(2, 2), (4, 2), (6, 3), (6, 2), (8, 4)],
        "PART_TO_PART_RATIO": [(1, 2), (2, 3), (3, 4), (2, 5), (1, 3)],
    }[interaction]

    valid: list[tuple[int, int, int, int]] = []
    for first, second in candidates:
        if interaction == "REMOVE" and first <= second:
            continue
        if interaction == "EQUAL_SHARING" and (second <= 0 or first % second != 0):
            continue
        result = _example_result(interaction, first, second)
        if (first, second) == (original_first, original_second):
            continue
        # Only the two inputs are ever spoken aloud, so only they must avoid the
        # hidden answer. The example's own result is never stated, so it may
        # coincide freely -- excluding it used to force a *larger* example.
        if answer in {first, second}:
            continue
        strictly_smaller = int(result <= original_scale and max(first, second) <= max(original_first, original_second))
        both_inputs_different = int(first != original_first and second != original_second)
        score = strictly_smaller * 100 + both_inputs_different * 20 - result
        valid.append((score, first, second, result))

    if not valid:
        # This is only a defensive path for unusually tiny questions.
        fallback = (1, 1) if interaction != "REMOVE" else (2, 1)
        first, second = fallback
    else:
        _, first, second, _ = max(valid)

    role_names = {
        "JOIN": ("starting objects", "joining objects"),
        "REMOVE": ("starting objects", "objects that leave"),
        "EQUAL_GROUPS": ("groups", "objects in each group"),
        "EQUAL_SHARING": ("objects to share", "recipients"),
        "PART_TO_PART_RATIO": ("objects in the first collection", "objects in the second collection"),
    }[interaction]
    return {
        "first": first,
        "second": second,
        "first_role": role_names[0],
        "second_role": role_names[1],
        "different_from_current_problem": (first, second) != (original_first, original_second),
        "result_is_hidden": True,
    }


def correction_plan(question: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    interaction = question["interaction"]
    unknown = question.get("unknown_position")
    plan: dict[str, Any] = {
        "interaction": interaction,
        "object": object_phrase(question, 1),
        "objects": object_phrase(question, 2),
        "student_correct": facts["student_correct"],
        "safe_numbers": [],
    }
    if facts["student_correct"]:
        plan["safe_next_step"] = "Acknowledge that the arrangement matches the story without stating any number."
        return plan

    if interaction == "JOIN" and facts.get("join_mode") == "two_parts":
        # Change from v4: in the two-part modes Unity clamps added_count at 0, so v4's
        # advice ("move N more") could be wrong (e.g. 0 + 7 when the story is 7 + 2).
        # Plan on the two parts directly.
        a, b = facts["learner_part_a_count"], facts["learner_part_b_count"]
        initial, change = facts["expected_initial_count"], facts["expected_added_count"]
        plan["observation"] = f"The first part shows {a} and the second part shows {b}."
        if b > change and unknown != "CHANGE":
            difference = b - change
            plan["safe_numbers"] = [a, b, change, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Return {difference} {object_phrase(question, difference)} from the second part, so it matches the story."
        elif b > change:
            plan["safe_numbers"] = [a, b]
            plan["safe_next_step"] = "Compare the second part with the story; it has more than the story needs. Do not state how many."
        elif a != initial:
            difference = abs(initial - a)
            plan["safe_numbers"] = [a, b, initial, difference]
            plan["movement_amount"] = difference
            if a < initial:
                plan["safe_next_step"] = f"Add {difference} more {object_phrase(question, difference)} to the first part."
            else:
                plan["safe_next_step"] = f"Return {difference} {object_phrase(question, difference)} from the first part."
        elif unknown == "CHANGE":
            plan["safe_numbers"] = [a, b]
            plan["safe_next_step"] = (
                "Compare the whole collection with the ending quantity stated in the story, then adjust the second part. "
                "Do not state how many objects must join."
            )
        else:
            difference = change - b
            plan["safe_numbers"] = [a, b, change, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Add {difference} more {object_phrase(question, difference)} to the second part."
        if facts.get("work_correct"):
            plan["observation"] = "The two parts match the story, but the optional number field does not agree with the visible work."
            plan["safe_numbers"] = []
            plan.pop("movement_amount", None)
            plan["safe_next_step"] = "Count the visible collection and make the number field agree with the arrangement, without saying the number aloud."

    elif interaction == "JOIN":
        learner = facts["learner_added_count"]
        expected = facts["expected_added_count"]
        if unknown == "CHANGE":
            plan["observation"] = f"The arrangement currently shows {learner} joining {object_phrase(question, learner)}."
            plan["safe_numbers"] = [learner]
            plan["safe_next_step"] = (
                "Compare the ending collection with the ending quantity stated in the story, then adjust the joining objects. "
                "Do not state how many objects must join."
            )
        elif learner < expected:
            difference = expected - learner
            plan["observation"] = f"The arrangement shows {learner} joining objects, while the story states {expected}."
            plan["safe_numbers"] = [learner, expected, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Move {difference} more {object_phrase(question, difference)} from the object bank into the collection."
        elif learner > expected:
            difference = learner - expected
            plan["observation"] = f"The arrangement shows {learner} joining objects, while the story states {expected}."
            plan["safe_numbers"] = [learner, expected, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Return {difference} {object_phrase(question, difference)} to the object bank."
        else:
            plan["observation"] = "The joining action matches the story, but the optional number field does not agree with the visible work."
            plan["safe_next_step"] = "Count the visible collection and make the number field agree with the arrangement, without saying the number aloud."

    elif interaction == "REMOVE":
        learner = facts["learner_removed_count"]
        expected = facts["expected_removed_count"]
        if unknown == "CHANGE":
            plan["observation"] = f"The arrangement currently shows {learner} removed {object_phrase(question, learner)}."
            plan["safe_numbers"] = [learner]
            plan["safe_next_step"] = (
                "Compare the remaining collection with the ending quantity stated in the story, then adjust the removed objects. "
                "Do not state how many objects were removed."
            )
        elif learner < expected:
            difference = expected - learner
            plan["observation"] = f"The arrangement shows {learner} removed objects, while the story states {expected} leave."
            plan["safe_numbers"] = [learner, expected, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Move {difference} more {object_phrase(question, difference)} into the removed area."
        elif learner > expected:
            difference = learner - expected
            plan["observation"] = f"The arrangement shows {learner} removed objects, while the story states {expected} leave."
            plan["safe_numbers"] = [learner, expected, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Return {difference} {object_phrase(question, difference)} to the starting collection."
        else:
            plan["observation"] = "The removal action matches the story, but the optional number field does not agree with the visible work."
            plan["safe_next_step"] = "Count the relevant visible objects and make the number field agree, without saying the number aloud."

    elif interaction == "EQUAL_GROUPS":
        group_count = facts["learner_group_count"]
        expected_count = facts["expected_group_count"]
        expected_size = facts["expected_group_size"]
        sizes = facts["learner_group_sizes"]
        if group_count < expected_count:
            difference = expected_count - group_count
            plan["observation"] = f"The arrangement has {group_count} groups, while the story describes {expected_count}."
            plan["safe_numbers"] = [group_count, expected_count, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Create {difference} more group area{'s' if difference != 1 else ''}."
        elif group_count > expected_count:
            difference = group_count - expected_count
            plan["observation"] = f"The arrangement has {group_count} groups, while the story describes {expected_count}."
            plan["safe_numbers"] = [group_count, expected_count, difference]
            plan["movement_amount"] = difference
            plan["safe_next_step"] = f"Remove {difference} extra group area{'s' if difference != 1 else ''}, moving any objects back first."
        else:
            wrong_index = next((i for i, size in enumerate(sizes) if size != expected_size), None)
            if wrong_index is not None:
                size = sizes[wrong_index]
                difference = abs(expected_size - size)
                plan["observation"] = f"Group {wrong_index + 1} has {size} objects, while the story states {expected_size} in each group."
                plan["safe_numbers"] = [wrong_index + 1, size, expected_size, difference]
                plan["movement_amount"] = difference
                if size < expected_size:
                    plan["safe_next_step"] = f"Add {difference} {object_phrase(question, difference)} to {region_name(question, 'group', wrong_index)}."
                else:
                    plan["safe_next_step"] = f"Return {difference} {object_phrase(question, difference)} from {region_name(question, 'group', wrong_index)} to the object bank."
            elif facts["undistributed_count"] > 0:
                remaining = facts["undistributed_count"]
                plan["observation"] = f"There are {remaining} objects still in the object bank."
                plan["safe_numbers"] = [remaining]
                plan["safe_next_step"] = "Finish placing the bank objects while keeping every group the same size described in the story."
            else:
                plan["observation"] = "The groups match the story, but the optional number field does not agree with the visible work."
                plan["safe_next_step"] = "Count all visible objects and make the number field agree, without stating the total aloud."

    elif interaction == "PART_TO_PART_RATIO":
        a = facts["learner_part_a"]
        b = facts["learner_part_b"]
        ea = facts["expected_part_a"]
        eb = facts["expected_part_b"]
        plan["observation"] = f"The two labelled collections currently show {a} and {b} objects."
        plan["safe_numbers"] = [a, b, ea, eb]
        if a != ea:
            plan["safe_next_step"] = "Compare the first labelled collection with the first quantity in the story, then adjust only that collection."
        elif b != eb:
            plan["safe_next_step"] = "Compare the second labelled collection with the second quantity in the story, then adjust only that collection."
        else:
            plan["safe_next_step"] = "Check that the two collection labels follow the same order as the ratio named in the question."

    else:
        sizes = facts["learner_share_sizes"]
        if facts["undistributed_count"] > 0:
            smallest = min(range(len(sizes)), key=lambda i: sizes[i]) if sizes else 0
            remaining = facts["undistributed_count"]
            plan["observation"] = f"There are {remaining} objects still in the bank, and the current share sizes are {sizes}."
            plan["safe_numbers"] = [remaining, smallest + 1, *sizes]
            plan["safe_next_step"] = f"Give the next {object_phrase(question, 1)} to {region_name(question, 'recipient', smallest)}, then keep the shares balanced."
        elif sizes and len(set(sizes)) > 1:
            low = min(range(len(sizes)), key=lambda i: sizes[i])
            high = max(range(len(sizes)), key=lambda i: sizes[i])
            plan["observation"] = f"The current share sizes are {sizes}."
            plan["safe_numbers"] = [low + 1, high + 1, *sizes]
            plan["safe_next_step"] = f"Move one {object_phrase(question, 1)} from {region_name(question, 'recipient', high)} to {region_name(question, 'recipient', low)}."
        else:
            plan["observation"] = "The sharing arrangement is equal, but the optional number field does not agree with the visible work."
            plan["safe_next_step"] = "Use one recipient's visible share to complete the number field, without stating the share size aloud."

    return plan


def student_facing_step(step: str) -> str:
    step = re.sub(
        r"^(?:please\s+)?ask\s+(?:the\s+)?(?:student|learner|you)\s+(?:to\s+)?",
        "",
        step.strip(),
        flags=re.IGNORECASE,
    )
    step = re.sub(r"\bthe student\b", "you", step, flags=re.IGNORECASE)
    step = re.sub(r"\bthe learner\b", "you", step, flags=re.IGNORECASE)
    if step:
        step = step[0].upper() + step[1:]
    return step


def _visible_safe_numbers(facts: dict[str, Any], answer: int) -> set[int]:
    safe: set[int] = set()
    keys = {
        "learner_added_count",
        "learner_part_a_count",   # Change from v4: two-part JOIN counts are visible too
        "learner_part_b_count",
        "learner_removed_count",
        "learner_group_count",
        "learner_part_a",
        "learner_part_b",
        "unassigned_a",
        "unassigned_b",
        "undistributed_count",
    }
    for key in keys:
        value = facts.get(key)
        if isinstance(value, int) and value != answer:
            safe.add(value)
    for key in ("learner_group_sizes", "learner_share_sizes"):
        for value in facts.get(key, []) or []:
            if isinstance(value, int) and value != answer:
                safe.add(value)
    return safe


def strategy_context(
    question: dict[str, Any],
    facts: dict[str, Any],
    support_type: SupportType,
) -> dict[str, Any]:
    support = SUPPORT_OPTIONS[support_type]
    plan = correction_plan(question, facts)
    plan["safe_next_step"] = student_facing_step(plan.get("safe_next_step", ""))
    example = _smaller_example(question) if support_type == "SMALLER_EXAMPLE" else None

    if support_type == "SMALLER_EXAMPLE" and example is not None:
        allowed_numbers = {int(example["first"]), int(example["second"])}
    elif support_type == "INTERFACE_HELP":
        allowed_numbers = set()
    else:
        allowed_numbers = set(safe_given_quantities(question).values())
        allowed_numbers.update(_visible_safe_numbers(facts, hidden_answer(question)))
        allowed_numbers.update(int(value) for value in plan.get("safe_numbers", []) if isinstance(value, int))

    # A quantity the story states, or the number of objects to move next, stays
    # quotable even when it happens to equal the hidden result: the learner can
    # already read it. Only a number with no such justification is withheld, and
    # the response validator separately blocks any phrasing that states the result.
    if not facts["student_correct"]:
        answer = hidden_answer(question)
        justified = set(safe_given_quantities(question).values())
        justified.update(int(value) for value in plan.get("safe_numbers", []) if isinstance(value, int))
        if answer not in justified:
            allowed_numbers.discard(answer)

    roles: dict[int, set[str]] = {}

    def _tag(value: Any, role: str) -> None:
        if isinstance(value, int) and value in allowed_numbers:
            roles.setdefault(value, set()).add(role)

    for value in safe_given_quantities(question).values():
        _tag(value, "story")
    for value in _visible_safe_numbers(facts, hidden_answer(question)):
        _tag(value, "visible")
    for value in plan.get("safe_numbers", []):
        _tag(value, "visible")
    if isinstance(plan.get("movement_amount"), int):
        movement = plan["movement_amount"]
        roles.setdefault(movement, set())
        # a movement amount is only a movement unless something else justifies it
        if movement not in set(safe_given_quantities(question).values()) and movement not in _visible_safe_numbers(facts, hidden_answer(question)):
            roles[movement] = {"movement"}
        else:
            roles[movement].add("movement")
    if example is not None:
        for value in (example.get("first"), example.get("second")):
            _tag(value, "example")

    context: dict[str, Any] = {
        "support_type": support_type,
        "number_roles": {str(number): sorted(role) for number, role in sorted(roles.items())},
        "support_goal": support["goal"],
        "given_quantities": safe_given_quantities(question),
        "current_arrangement": _safe_current_state(facts),
        "correction_plan": plan,
        "allowed_numbers_in_response": sorted(allowed_numbers),
    }
    if support_type == "INTERFACE_HELP":
        context["interface_controls"] = _interface_controls(question)
    elif support_type == "SIMPLIFY_STORY":
        context["story_structure"] = _story_structure(question)
    elif support_type == "SMALLER_EXAMPLE":
        context["smaller_example"] = example
    return context


def _safe_current_state(facts: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "interaction",
        "construction_status",
        "learner_added_count",
        "learner_part_a_count",
        "learner_part_b_count",
        "learner_removed_count",
        "learner_group_count",
        "learner_group_sizes",
        "learner_share_sizes",
        "learner_part_a",
        "learner_part_b",
        "unassigned_a",
        "unassigned_b",
        "undistributed_count",
        "answer_entered",
        "answer_supported_by_work",
        "work_correct",
        "student_correct",
    }
    return {key: value for key, value in facts.items() if key in keys}


def _interface_controls(question: dict[str, Any]) -> list[str]:
    interaction = question["interaction"]
    common = [
        "Drag an object, or click it and then click a destination.",
        "Use Undo for the last move and Reset to start the question again.",
    ]
    if interaction == "JOIN":
        return ["Move joining objects from the object bank into the collection."] + common
    if interaction == "REMOVE":
        return ["Move objects from the starting collection into the removed area."] + common
    if interaction == "EQUAL_GROUPS":
        return [
            "Use Add group to create containers, then move objects from the bank into each group.",
            "Copy group duplicates the layout of a completed group when appropriate.",
        ] + common
    if interaction == "EQUAL_SHARING":
        return ["Move objects from the bank into the recipient areas, keeping the shares balanced."] + common
    return ["Move each kind of object from its bank into the matching labelled collection."] + common


def _story_structure(question: dict[str, Any]) -> dict[str, str]:
    interaction = question["interaction"]
    if interaction == "JOIN":
        return {
            "first": "A collection is already present.",
            "change": "Another collection joins it.",
            "task": "Represent both parts without calculating the final answer for the student.",
        }
    if interaction == "REMOVE":
        return {
            "first": "A starting collection is present.",
            "change": "Some objects leave it.",
            "task": "Show what leaves and what remains without stating the final answer.",
        }
    if interaction == "EQUAL_GROUPS":
        return {
            "first": "The story gives a number of groups.",
            "relationship": "Every group contains the same stated amount.",
            "task": "Build the repeated groups without stating the total.",
        }
    if interaction == "EQUAL_SHARING":
        return {
            "first": "The story gives a total collection and recipients.",
            "relationship": "Every recipient must receive an equal share.",
            "task": "Distribute all objects without stating the share size.",
        }
    return {
        "first": "The story gives two labelled parts in a specific order.",
        "relationship": "The two collections must show those stated quantities and labels.",
        "task": "Build both labelled collections in the requested ratio order.",
    }


def recovery_variants(question: dict[str, Any], facts: dict[str, Any], support_type: SupportType, conversational_strategy: str | None = None) -> list[str]:
    plan = correction_plan(question, facts)
    step = student_facing_step(plan.get("safe_next_step", "Compare the arrangement with the story and revise one part."))
    objects = object_phrase(question, 2)

    if conversational_strategy == "RECOUNT_AND_COMPARE" and not facts["student_correct"]:
        interaction = question["interaction"]
        variants = {
            "JOIN": [
                "Compare the current collection with the story. What is still different?",
                "Look at the objects already moved and those still in the object bank. Does the arrangement match the story?",
                "Count what is currently in the collection and compare it with the joining action in the story.",
                "Without moving anything, check the current collection against the story. What do you notice?",
            ],
            "REMOVE": [
                "Compare what you removed with what the story describes. Do they match?",
                "Look at the starting collection and the removed area. Is the removal complete?",
                "Count what you removed and compare that count with the story. What do you notice?",
                "Without moving anything, check the removed objects against the story.",
            ],
            "EQUAL_GROUPS": [
                "Compare the number of groups and the objects in each group with the story. What do you notice?",
                "Look at each group. Do the group count and group sizes match the story?",
                "Check each group and the objects still in the object bank. Is the arrangement complete?",
                "Without moving anything, compare each group with the story.",
            ],
            "EQUAL_SHARING": [
                "Compare the shares. Do all recipients currently have the same number?",
                "Look at each recipient's share. Are any of the shares different?",
                "Check the object bank and each recipient's share. Is the sharing complete and equal?",
                "Without moving anything, compare the shares each recipient has.",
            ],
            "PART_TO_PART_RATIO": [
                "Compare the two labelled collections with the two parts named in the question. Do both match?",
                "Look at the first and second collections. Are the labels and counts in the requested order?",
                "Check each labelled collection against the story. Is either part incomplete?",
                "Without moving anything, compare both parts with the ratio order in the question.",
            ],
        }
        return variants[interaction]

    if facts["student_correct"]:
        interaction = question["interaction"]
        if interaction == "EQUAL_GROUPS":
            return [
                "Your groups now match the relationship in the story. Nice work.",
                "The groups and their contents now fit the story. Well done.",
                "Your grouped arrangement is consistent with the story. Good thinking.",
            ]
        if interaction == "EQUAL_SHARING":
            return [
                "The sharing is now fair and matches the story. Nice work.",
                "Your sharing arrangement now fits the story. Well done.",
                "Every part of the sharing now agrees with the story. Good thinking.",
            ]
        if interaction == "PART_TO_PART_RATIO":
            return [
                "Both labelled collections now match the ratio named in the question. Nice work.",
                "The two parts and their order now fit the story. Well done.",
                "Your ratio representation now agrees with both labelled quantities. Good thinking.",
            ]
        return [
            f"Your {objects} now represent the story clearly. Nice work.",
            "The arrangement now matches the change described in the story. Well done.",
            "You revised the work so it fits the story. Good thinking.",
        ]

    if support_type == "INTERFACE_HELP":
        controls = _interface_controls(question)
        return [
            f"Use the object bank and current arrangement. {controls[0]}",
            f"Use the object bank and current arrangement. {controls[-1]}",
            "In the current arrangement, select an object from the object bank and then select where you want it to go. Undo reverses the last move, and Reset restores the starting arrangement.",
        ]

    if support_type == "SIMPLIFY_STORY":
        interaction = question["interaction"]
        if interaction == "JOIN":
            return [
                f"The story has two parts: the {objects} already together and the {objects} that join later. Show those two parts in that order.",
                f"First notice the {objects} already present. Then represent only the new {objects} that arrive.",
            ]
        if interaction == "REMOVE":
            return [
                f"The story begins with one collection of {objects}, and then some leave. Show what was there first and what moves away.",
                f"Focus on two parts: the starting {objects} and the {objects} taken away afterward.",
            ]
        if interaction == "EQUAL_GROUPS":
            return [
                f"The story tells how many groups to make and how many {objects} belong in every group. Represent those two roles separately.",
                f"First make the groups described in the story, then place the same stated amount of {objects} in each one.",
            ]
        if interaction == "EQUAL_SHARING":
            return [
                f"The story gives one collection of {objects} and several recipients. Share the objects so every recipient gets the same amount.",
                f"Think about fair sharing: use every {object_phrase(question, 1)} and keep the recipient amounts equal.",
            ]
        return [
            "The story names two parts in a particular order. Build the first labelled collection and the second labelled collection to match those stated parts.",
            "Focus on the two labels and their order in the question, then make each collection match its stated part.",
        ]

    if support_type == "SMALLER_EXAMPLE":
        example = _smaller_example(question)
        first, second = example["first"], example["second"]
        if question["interaction"] == "JOIN":
            return [
                f"Try a smaller example: start with {first} counters and let {second} more join. Show the two parts with objects, but leave the result unanswered.",
                f"Imagine a smaller story with {first} counters already present and {second} counters joining. Represent both sets without solving it.",
                f"Use counters for this smaller example: show {first} at the start, then bring in {second} more. Keep the result blank.",
            ]
        if question["interaction"] == "REMOVE":
            return [
                f"Try a smaller example: begin with {first} counters and move {second} away. Show the action without finding the final amount.",
                f"Imagine a smaller story that starts with {first} counters and has {second} leave. Represent the movement without solving it.",
                f"Use counters for this smaller example: place {first} at the start and move {second} away. Keep the result blank.",
            ]
        if question["interaction"] == "EQUAL_GROUPS":
            return [
                f"Try a smaller example: make {first} groups and place {second} counters in each. Notice which number controls the groups and which controls each group.",
                f"Imagine a smaller grouped story with {first} groups and {second} counters in every group. Build it without finding the total.",
                f"Use counters for this smaller example: create {first} groups, then put {second} in each group. Leave the total blank.",
            ]
        if question["interaction"] == "PART_TO_PART_RATIO":
            return [
                f"Try a smaller example: build a first collection with {first} counters and a second collection with {second} counters. Keep the order visible.",
                f"Imagine a smaller ratio story with {first} of one kind and {second} of another. Build the two labelled parts in that order.",
                f"Use counters for this smaller example: place {first} in the first labelled area and {second} in the second.",
            ]
        return [
            f"Try a smaller example: share {first} counters among {second} recipients. Distribute them fairly, but leave the share size unanswered.",
            f"Imagine a smaller sharing story with {first} counters and {second} recipients. Show fair sharing without finding the share size.",
            f"Use counters for this smaller example: distribute {first} among {second} recipients. Keep the share size blank.",
        ]

    if support_type == "HINT":
        return [
            step,
            f"Try just this one step: {step}",
            f"Focus on one change in your {objects}: {step}",
            f"Here is one small hint: {step}",
        ]

    if support_type == "UNSURE":
        return [
            f"It is okay to be unsure. {step}",
            f"This part can be confusing. Let us focus on one change: {step}",
            f"Not knowing yet is okay. Compare one phrase in the story with your {objects}, then try this: {step}",
        ]

    return [
        step,
        f"Look closely at the current {objects}. {step}",
        f"Compare this part with the matching words in the story. {step}",
    ]


def choose_recovery_variant(
    question: dict[str, Any],
    facts: dict[str, Any],
    support_type: SupportType,
    turn_index: int,
) -> str:
    variants = recovery_variants(question, facts, support_type)
    seed = f"{question['id']}:{support_type}:{turn_index}".encode("utf-8")
    return variants[int(hashlib.sha256(seed).hexdigest(), 16) % len(variants)]
