"""Fixed responses: correctness confirmations, fallbacks, and neutral messages.

Ported from v4 `tutor_service._safe_recovery`. Every candidate text passes the
same answer-protection and support-type checks as an LLM reply before it is
used. Order (v4):

1. v4 recovery variants for the support type, rotated by history length
2. the per-support emergency text
3. for SMALLER_EXAMPLE, the rebuilt example
4. any of the above that passes every hard check except repetition (least similar to recent turns)
5. Change from v4: instead of raising (which v4 turned into HTTP 503), a
   predetermined safe message with no numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from app.answer_protection import check_response, similarity
from app.strategies import recovery_variants

# Returned when no checked candidate passes. Contains no number and no hint.
SAFE_MESSAGE = "Let's look at your work and the story together. Compare one part of your arrangement with the story."

# Returned when the request or learner state cannot be used (layer 1 / layer 2 rejection).
NEUTRAL_MESSAGE = "Let's keep working on the story. Try your next step, and ask me again if you need help."


@dataclass(frozen=True)
class Fallback:
    text: str
    source: str              # "variant:<i>", "emergency", "example", "least_similar", "safe_message"
    passed_checks: bool      # True if `text` passed check_response (with or without repetition)
    first_failed_rule: Optional[str] = None   # rule that rejected the first candidate (for the log)


def _emergency(question: Mapping[str, Any], support_type: str) -> Optional[str]:
    """v4 emergency texts, unchanged."""
    hint = {
        "JOIN": "Focus on the objects that join. Look at the object bank and make a small change that better matches the story.",
        "REMOVE": "Focus on the objects that leave. Look at the removed area and make a small change that better matches the story.",
        "EQUAL_GROUPS": "Focus on the groups already built. Look at a group and make a small change that better matches the story.",
        "EQUAL_SHARING": "Focus on the current shares. Compare two recipient areas and make a small change toward equal sharing.",
        "PART_TO_PART_RATIO": "Focus on the two labelled collections. Compare each part and its order with the ratio named in the question.",
    }.get(question.get("interaction"))
    return {
        "INTERFACE_HELP": "Use the object bank and current arrangement: drag an object to its destination, or select the object and then select where it should go. Undo reverses the last move, and Reset starts the question again.",
        # Change from v4: one story-help text per type; v4's single text described a
        # change over time, which does not fit groups, sharing or ratio.
        "SIMPLIFY_STORY": {
            "JOIN": "Read the story in two parts: what is there first and what joins it. Show those parts with the objects.",
            "REMOVE": "Read the story in two parts: what is there first and what is taken away. Show those parts with the objects.",
            "EQUAL_GROUPS": "The story tells how many groups there are and how much goes in each group. Show the groups with the objects.",
            "EQUAL_SHARING": "The story tells how many objects there are and who shares them equally. Show the sharing with the objects.",
            "PART_TO_PART_RATIO": "The story names two parts to compare, in order. Show each part with the objects.",
        }.get(question.get("interaction"), "Read the story again and show what it says with the objects."),
        "CHECK_WORK": "Compare one part of your arrangement with the matching words in the story, then revise only that part.",
        "AUTO_CHECK": "Compare the part you just changed with the matching words in the story, then revise that part.",
        "HINT": hint,
        "UNSURE": "It is okay to be unsure. Focus on one phrase in the story and match it to one part of your arrangement.",
        "OPEN_ENDED": "Let us use your current work to think about that. Compare one part of your arrangement with the matching part of the story and tell me what you notice.",
    }.get(support_type)


def _example(question: Mapping[str, Any], context: Mapping[str, Any]) -> Optional[str]:
    """v4 SMALLER_EXAMPLE rebuild."""
    example = context.get("smaller_example")
    if not example:
        return None
    first, second = example["first"], example["second"]
    return {
        "JOIN": f"Try a smaller example: start with {first} counters and let {second} more join. Show the two parts, but leave the result unanswered.",
        "REMOVE": f"Try a smaller example: begin with {first} counters and move {second} away. Show the action, but leave the result unanswered.",
        "EQUAL_GROUPS": f"Try a smaller example: make {first} groups and place {second} counters in each. Leave the total unanswered.",
        "EQUAL_SHARING": f"Try a smaller example: share {first} counters among {second} recipients. Leave the share size unanswered.",
    }.get(question["interaction"],
          f"Try a smaller example: build {first} counters in the first labelled collection and {second} in the second.")


# An instruction to move a specific amount: a move verb followed closely by a number,
# "the next" or "another" ("Move 2 more cookies", "Create 4 more group areas",
# "Give the next cinnamon swirl to Jane", "Return 1 cookie").
_EXACT_MOVE = re.compile(
    r"\b(?:move|moves|put|place|add|give|return|take|remove|create|make|drag|bring|send|share)\b"
    r"[^.!?]{0,20}?\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"the next|another)\b",
    re.IGNORECASE,
)


def states_exact_move(text: str) -> bool:
    """True if the text tells the learner exactly how many objects to move."""
    return bool(_EXACT_MOVE.search(text))


def _visibility_safe(text: str, pov_context: Mapping[str, Any] | None) -> str:
    """Replace a fixed look-at instruction when its target is not fully visible.

    This is intentionally narrow: never infer object locations or rename unseen regions.
    """
    if not pov_context:
        return text
    for region in pov_context.get("regions", []):
        name = str(region.get("region_name") or "")
        if not name:
            continue
        aliases = [name]
        if name == "the removed objects area":
            aliases.append("the removed area")
        for alias in aliases:
            pattern = re.compile(r"\bLook at " + re.escape(alias) + r"\b", re.IGNORECASE)
            if not pattern.search(text):
                continue
            visibility = region.get("visibility")
            if visibility == "not_visible":
                replacement = ("Turn toward " + alias if region.get("learner_has_seen_name")
                               else "Turn to find the area for this part of the story")
                text = pattern.sub(replacement, text)
            elif visibility == "partially_visible":
                text = pattern.sub("Adjust your view toward " + alias, text)
    return text


def choose_fallback(question, request, facts, context, *, pov_context=None) -> Fallback:
    """Return the first fixed text that passes every check (v4 order).

    Change from v4: a fallback replaces an LLM reply that failed or was
    blocked, so it must not be more revealing than a gentle hint. v4's next-step
    variants often state the exact move ("Move 2 more cookies into the removed
    area"); those are skipped. What remains are story-grounded texts that point at
    the mismatch without the corrective quantity, then the safe message.
    SMALLER_EXAMPLE keeps its example numbers (they are not a corrective move).
    """
    variants = recovery_variants(question, facts, request.support_type)
    offset = len(request.conversation_history)
    rotated = variants[offset % len(variants):] + variants[:offset % len(variants)] if variants else []

    allow_moves = request.support_type == "SMALLER_EXAMPLE"
    candidates: list[tuple[str, str]] = [
        (text, f"variant:{variants.index(text)}") for text in rotated
        if allow_moves or not states_exact_move(text)
    ]
    # v3: a generic "compare the shares" makes no sense before anything is shared.
    if (question.get("interaction") == "EQUAL_SHARING" and not allow_moves
            and facts.get("learner_share_sizes") and not any(facts["learner_share_sizes"])
            and request.support_type in {"HINT", "CHECK_WORK", "AUTO_CHECK", "UNSURE"}):
        candidates.insert(0, ("Nothing has been shared yet. Look at the story, then start by giving out some of the objects, one to each friend at a time.", "state_specific"))
    emergency = _emergency(question, request.support_type)
    if emergency:
        candidates.append((emergency, "emergency"))
    if not facts.get("student_correct") and not allow_moves:
        # v4's neutral inspection texts (RECOUNT_AND_COMPARE): no move, so a repeated
        # request does not have to hear the same sentence again.
        neutral = recovery_variants(question, facts, request.support_type, "RECOUNT_AND_COMPARE")
        neutral = neutral[offset % len(neutral):] + neutral[:offset % len(neutral)] if neutral else []
        candidates += [(text, "neutral") for text in neutral if not states_exact_move(text)]
    if request.support_type == "SMALLER_EXAMPLE":
        example = _example(question, context)
        if example:
            candidates.append((example, "example"))

    # Transform candidate wording before safety validation; this does not change
    # baseline behavior, which has no POV context.
    if pov_context is not None:
        candidates = [(_visibility_safe(text, pov_context), source) for text, source in candidates]

    first_failed: Optional[str] = None
    for text, source in candidates:
        rule = check_response(text, question, request, facts, context)
        if rule is None:
            return Fallback(text, source, True, first_failed)
        first_failed = first_failed or rule

    # v4: repetition is soft. Use the hard-safe candidate least similar to recent turns.
    recent = [m.content for m in request.conversation_history[-12:] if m.role == "tutor"]
    hard_safe = [text for text, _ in candidates
                 if check_response(text, question, request, facts, context, check_repetition=False) is None]
    if hard_safe:
        best = min(hard_safe, key=lambda c: max((similarity(c, old) for old in recent), default=0.0))
        return Fallback(best, "least_similar", True, first_failed)

    return Fallback(SAFE_MESSAGE, "safe_message", False, first_failed)


def confirmation(question, request, facts, context) -> Fallback:
    """Fixed confirmation for a correct construction (no LLM call, no numbers)."""
    return choose_fallback(question, request, facts, context)
