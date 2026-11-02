"""The tutor prompt. Versioned; the version is logged with every request.

The rules are v4's (`tutor_service._freeform_reasoning_prompt`), reduced to one
child-facing field. The LLM never judges correctness: it receives the
evaluator's verdict and the verified arrangement, and writes the wording only.

The payload never contains the hidden answer, the formula, or any `expected_*`
value. Only quantities the story states openly and the learner's own visible
counts are included (tested).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from app.evaluator import Evaluation
from app.schemas import TutorRequest
from app.strategies import SUPPORT_OPTIONS, region_name, safe_given_quantities

PROMPT_VERSION = "step1-v2"                       # default; step1-v1 kept for comparison
PROMPT_VERSIONS = ("step1-v1", "step1-v2", "step3-pov-v2", "step3-pov-v3", "step3-pov-v4", "step3-pov-v5")
MAX_WORDS = 45
HISTORY_TURNS = 10

POV_RULES = """VR viewpoint guidance (additional to the rules above):
- Visibility describes the learner's view, not mathematical correctness.
- Adapt spatial wording only; use the verified mathematical evaluation unchanged.
- Do not imply an area is visible when it is not visible.
- A partially visible area may contain objects outside the learner's view.
- When learner_has_seen_name is false, avoid relying on that region name; use grounded descriptive wording instead.
- When necessary, invite the learner to look toward an area without claiming it is visible.
- When visibility is uncertain, use neutral language.
- Do not reveal answers or invent scene details.
"""


POV_RULES_V2 = """VR viewpoint guidance (revised, spatial wording only):
- The verified mathematical state is authoritative; viewpoint information is not evidence of correctness.
- Before suggesting an action, identify the relevant region from the verified task and the supplied viewpoint regions.
- If that region is not_visible and its label was seen, first invite the learner to turn toward that named area.
- If that region is not_visible and its label was never seen, describe its role using the story rather than assuming the learner knows its name.
- If partially_visible, do not assume all objects there are visible; suggest adjusting the view only if needed.
- If mostly_visible, give a single small grounded action without redundant turning instructions.
- If visibility is unknown or missing, do not claim the learner can see any particular region.
- Never claim an off-screen object is present or absent, reveal a hidden answer, or invent an object location.
- Give at most one small tutoring action; avoid combining turning, counting, and moving into multiple tasks.
"""


POV_RULES_V3 = """VR viewpoint guidance (v3, spatial wording only):
- The verified mathematical state is authoritative; viewpoint information is not evidence of correctness.
- Identify the relevant region from the verified task and the supplied viewpoint regions.
- If that region is not_visible and its name was seen: say one short phrase turning the learner toward it (for example "Turn toward <name>"), then add ONE question about the matching part of the story. Never turn the learner without giving that question.
- If that region is not_visible and its name was never seen: describe its role using the story, not its name, and ask one question about the story.
- If partially_visible: do not assume all objects there are visible; adjust the view only if needed.
- If mostly_visible: no turning words; just the question or step.
- If visibility is unknown or missing, do not claim the learner can see any particular region.
- Never claim an off-screen object is present or absent, reveal a hidden answer, or invent an object location.
- Never write a turning phrase in the same reply as the number of groups, parts or objects the story needs.
"""

V3_QUALITY_RULES = """10. Never put a region name in quotation marks and never use generic labels such as "the objects to share" or "the objects to try". Use the story's own people, object names and the labels the learner sees.
11. Prefer a gentle noticing prompt over a direct instruction. Do not tell the learner how many objects to move or add; point to the part of the story to match and let the learner decide. Every hint must contain exactly one clear action word the learner can do, such as look, check, compare, count or notice, then may end with a short question (for example "Check what the story says about Marcie's part. Does your collection match?"). Never reply with only a question and no action word, and do not use first, then or next.
12. Do not combine a place with the number the story needs (for example "Group 4 ... the story needs 3 groups").
13. Do not ask the learner to find or pick an object they cannot see; ask what the story says about that part instead.
"""


POV_RULES_V4 = """VR viewpoint guidance (v4, spatial wording only):
- The verified mathematical state is authoritative; viewpoint information is not evidence of correctness.
- Decide which region the learner still needs to work on, using arrangement_description, verified_errors and the story.
- If that region is not_visible and learner_has_seen_name is true: your reply MUST start with "Turn toward <region_name>." and then ask one question about the matching part of the story. Do not send the learner to a different, visible region instead.
- If that region is not_visible and learner_has_seen_name is false: describe its role using the story and start with "Turn to find the part of the story about <what it holds>." Do not use its name.
- If partially_visible: start with "Adjust your view toward <region_name>." only if the learner needs to see more of it; otherwise no turning words.
- If mostly_visible, or if the region the learner needs is visible: no turning words at all, even if some other region is out of view.
- If visibility is unknown or missing, do not claim the learner can see any particular region.
- Never claim an off-screen object is present or absent, reveal a hidden answer, or invent an object location.
- Never write a turning phrase in the same reply as the number of groups, parts or objects the story needs.
"""

V4_STYLE_RULES = """14. Mention one thing the learner has actually built, using object names and no counts, so the hint fits their work. Then ask one question that makes them look back at the matching words in the story.
15. Begin the reply with the word "{opening}" (unless a turn phrase is required first, in which case use the turn phrase and then continue with "{opening}"). Never begin two replies the same way.
"""

V5_STYLE_RULES = """14. Write at most two short sentences. If a turn phrase is required it is the first sentence, and the second sentence holds the one action word and one question about the story. Otherwise one sentence with one action word and one question is enough.
15. Sound like a friendly teacher talking to a 7-year-old. Do not start with "Tell me". Do not stack several action words. You may vary between look, check, compare, notice and count; do not always use the same one.
"""

OPENING_VERBS = ("Look", "Compare", "Count", "Find", "Show", "Notice", "Check", "Tell")


def _opening_verb(question: Mapping[str, Any], request: TutorRequest) -> str:
    import zlib
    key = f"{request.question_id}|{request.support_type}|{len(request.conversation_history)}|{getattr(request, 'student_message', '')}"
    return OPENING_VERBS[zlib.crc32(key.encode("utf-8")) % len(OPENING_VERBS)]


@dataclass(frozen=True)
class Prompt:
    instructions: str
    payload: str               # JSON string sent as the user message
    version: str = PROMPT_VERSION


def _subtype_guidance(question: Mapping[str, Any]) -> str:
    """v4 `_subtype_guidance`: extra framing when the joining amount is hidden."""
    if question.get("interaction") == "JOIN" and question.get("unknown_position") == "CHANGE":
        return (
            "This problem hides how many objects joined. Do not calculate, state, estimate, or reveal that "
            "quantity, and do not write the complete addition equation. Use the visible starting and ending "
            "collections to help the learner compare the two states.\n"
        )
    return ""


def _plural(question: Mapping[str, Any], label_key: str, fallback: str) -> str:
    visual = question.get("visual", {}) or {}
    label = str(visual.get(label_key) or fallback)
    return label if label.endswith("s") else label + "s"


def describe_arrangement(question: Mapping[str, Any], facts: Mapping[str, Any]) -> list[str]:
    """Plain sentences about what is already on the desk (prompt v2).

    Built only from the learner's own counts and quantities the story states
    openly, so it never contains the hidden answer as a target (tested).
    """
    i = question["interaction"]
    p = question["parameters"]
    unknown = question.get("unknown_position")
    objects = _plural(question, "object_label", "object")
    lines: list[str] = []

    def compare(have: int, target: int) -> str:
        return "complete" if have == target else ("fewer than the story" if have < target else "more than the story")

    if i == "JOIN":
        a, b = facts.get("learner_part_a_count"), facts.get("learner_part_b_count")
        first = _plural(question, "initial_object_label", "starting object")
        second = _plural(question, "change_object_label", "joining object")
        if facts.get("join_mode") == "two_parts":
            lines.append(f"{first[:1].upper()}{first[1:]} already placed: {a} (story: {p['initial']}, {compare(a, p['initial'])}).")
            if unknown == "CHANGE":
                lines.append(f"{second[:1].upper()}{second[1:]} already placed: {b}.")
            else:
                lines.append(f"{second[:1].upper()}{second[1:]} already placed: {b} (story: {p['change']}, {compare(b, p['change'])}).")
        else:
            current, added = facts["learner_final_count"], facts["learner_added_count"]
            lines.append(f"The collection already holds {current} {objects}; the story starts with {p['initial']}.")
            if added < 0:
                lines.append(f"{-added} of the starting {objects} have been taken out of the collection.")
            elif current >= p["initial"]:
                lines.append(f"All the starting {objects} are already in the collection.")
            if unknown == "CHANGE":
                lines.append(f"The story ends with {p['result']}.")
    elif i == "REMOVE":
        removed, remaining = facts["learner_removed_count"], facts["learner_remaining_count"]
        lines.append(f"The removed area already holds {removed} {objects}; {remaining} are still in the collection.")
        if unknown == "CHANGE":
            lines.append(f"The story starts with {p['initial']} and ends with {p['result']}.")
        else:
            lines.append(f"The story starts with {p['initial']} and removes {p['change']} ({compare(removed, p['change'])} removed so far).")
    elif i == "EQUAL_GROUPS":
        sizes = facts["learner_group_sizes"]
        count, size = p["group_count"], p["group_size"]
        lines.append(f"{len(sizes)} group(s) already exist; the story has {count} ({compare(len(sizes), count)}).")
        for k, value in enumerate(sizes):
            lines.append(f"{region_name(dict(question), 'group', k)} holds {value} (story: {size} in each, {compare(value, size)}).")
        if facts.get("undistributed_count"):
            lines.append(f"{facts['undistributed_count']} {objects} are not in any group.")
    elif i == "EQUAL_SHARING":
        sizes = facts["learner_share_sizes"]
        names = [region_name(dict(question), "recipient", k) for k in range(len(sizes))]
        lines.append(f"These recipient areas already exist: {', '.join(names)}. Do not ask the learner to create them.")
        lines.append("Current shares: " + ", ".join(f"{n} has {v}" for n, v in zip(names, sizes)) + ".")
        if not sizes or not any(sizes):
            lines.append("Nothing has been shared yet; every share is empty.")
        elif len(set(sizes)) == 1:
            lines.append("The shares are equal so far.")
        else:
            lines.append("The shares are not equal yet.")
        if facts.get("undistributed_count"):
            lines.append(f"{facts['undistributed_count']} {objects} have not been shared yet.")
    else:
        visual = question.get("visual", {}) or {}
        a_label = visual.get("part_a_label") or "first part"
        b_label = visual.get("part_b_label") or "second part"
        a, b = facts["learner_part_a"], facts["learner_part_b"]
        lines.append(f"Both collections already exist ({a_label} and {b_label}). Do not ask the learner to make a group or collection.")
        lines.append(f"{a_label}: {a} placed (story: {p['part_a']}, {compare(a, p['part_a'])}); "
                     f"{b_label}: {b} placed (story: {p['part_b']}, {compare(b, p['part_b'])}).")
        if facts.get("unassigned_a") or facts.get("unassigned_b"):
            lines.append(f"Not yet placed: {facts.get('unassigned_a', 0)} {a_label}, {facts.get('unassigned_b', 0)} {b_label}.")
    return lines


V2_RULES = """8. arrangement_description says what is already on the desk. Never tell the learner to place, add, make or create anything it says is already there or already complete.
9. The collections, groups and recipient areas it lists already exist. Ask for a new group only when it says there are fewer groups than the story.
"""


def build_prompt(
    question: Mapping[str, Any],
    request: TutorRequest,
    evaluation: Evaluation,
    context: Mapping[str, Any],
    version: str = PROMPT_VERSION,
    pov_context: Mapping[str, Any] | None = None,
) -> Prompt:
    """Build the prompt. `version` selects step1-v2 (default) or step1-v1 (earlier prompt)."""
    if version not in PROMPT_VERSIONS:
        raise ValueError(f"unknown prompt version {version!r}")
    support = SUPPORT_OPTIONS[request.support_type]
    instructions = f"""You are a math tutor for children aged 6 to 8, inside a virtual-reality activity where they build word problems with objects.
Python has already checked the learner's work. Use only the verified facts you are given. Never decide yourself whether the work is correct.
The learner asked for: {support['label']}. Goal: {support['goal']}

Rules:
1. Never reveal the final answer, and never give an operation that directly produces it.
2. Never invent learner actions, written answers, spoken claims, objects, people or relationships.
3. Use only numbers listed in allowed_numbers. Prefer no numbers.
4. Be brief (at most {MAX_WORDS} words), kind, and grounded in the visible arrangement. Use the object names given.
5. Story help explains what the story means; check-work asks the learner to inspect one part of the arrangement (do not tell them what to move); a hint gives exactly one small step.
6. If the learner wrote a message, answer it and stay on this problem. Do not tell stories, poems or jokes.
7. Do not repeat the wording of recent tutor messages.
{V2_RULES if version in {"step1-v2", "step3-pov-v2", "step3-pov-v3", "step3-pov-v4", "step3-pov-v5"} else ""}{V3_QUALITY_RULES if version in {"step3-pov-v3", "step3-pov-v4", "step3-pov-v5"} else ""}{V5_STYLE_RULES if version == "step3-pov-v5" else ""}{V4_STYLE_RULES.format(opening=_opening_verb(question, request)) if version == "step3-pov-v4" else ""}{_subtype_guidance(question)}
Return JSON with one field, "tutor_text": the sentence(s) the child will hear."""

    if pov_context is not None:
        instructions += "\n\n" + POV_RULES
        if version == "step3-pov-v2":
            instructions = instructions[: -len(POV_RULES)] + POV_RULES_V2
        elif version == "step3-pov-v3":
            instructions = instructions[: -len(POV_RULES)] + POV_RULES_V3
        elif version in {"step3-pov-v4", "step3-pov-v5"}:
            instructions = instructions[: -len(POV_RULES)] + POV_RULES_V4

    payload: dict[str, Any] = {
        "support_request": request.support_type,
        "interaction": question.get("interaction"),
        "unknown_position": question.get("unknown_position"),
        "hidden_role": question.get("hidden_role"),
        "problem": {
            "story": question.get("body"),
            "question": question.get("question"),
            "stated_quantities": safe_given_quantities(question),
        },
        "object_language": question.get("visual", {}),
        "verified_arrangement": context.get("current_arrangement", {}),
        "construction_status": evaluation.construction_status,
        "verified_errors": list(evaluation.errors),
        "allowed_numbers": context.get("allowed_numbers_in_response", []),
        "latest_action": request.latest_action or None,
        "learner_message": request.student_message.strip() or None,
        "recent_conversation": [m.model_dump() for m in request.conversation_history[-HISTORY_TURNS:]],
    }
    if evaluation.notes:
        payload["verified_notes"] = list(evaluation.notes)
    if version in {"step1-v2", "step3-pov-v2"}:
        payload["arrangement_description"] = describe_arrangement(question, evaluation.facts)
    state_note = request.learner_state.get("state_note")
    if isinstance(state_note, str) and state_note.strip():
        payload["state_note"] = state_note.strip()
    if request.support_type == "INTERFACE_HELP":
        payload["interface_controls"] = context.get("interface_controls", [])
    if request.support_type == "SMALLER_EXAMPLE":
        payload["smaller_example"] = context.get("smaller_example")
    if pov_context is not None:
        payload["vr_pov_context"] = dict(pov_context)
    return Prompt(instructions=instructions, payload=json.dumps(payload, ensure_ascii=False), version=version)
