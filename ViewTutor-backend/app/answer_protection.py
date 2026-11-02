"""Answer protection and response policy, ported from v4 `tutor_service.py`.

Every rule below is v4's, copied verbatim. The only change: `response_is_safe`
became `check_response`, which returns the name of the first rule a reply
breaks (or None if it passes), so the research log can record which rule fired
`response_is_safe` keeps v4's boolean interface.

Removed from v4 (Llama-specific, not policy): JSON extraction and key repair,
`clean_reply` word rewriting, object-spelling correction, third-person display
rewriting. Structured output replaces them; the LLM's text is never rewritten.

These are rule-based checks. They cannot guarantee that every indirect reveal is
caught; misses found in manual review become regression tests.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Optional

from app.evaluator import hidden_answer

# `request` below is an app.schemas.TutorRequest (support_type, student_message,
# conversation_history); `facts` is Evaluation.facts; `context` is strategies.strategy_context().


NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def _is_interface_message(message: str) -> bool:
    lowered = message.lower().strip()
    return bool(re.search(
        r"\b(?:drag|click|button|screen|undo|reset|object bank|"
        r"where (?:do i|should i|can i|to) (?:move|drag|place|put)|"
        r"how (?:do i|can i|should i|to) (?:move|add|place|drag|put)|"
        r"do not know where to (?:move|drag|place|put)|"
        r"don't know where to (?:move|drag|place|put))\b",
        lowered,
    ))


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def similarity(left: str, right: str) -> float:
    a, b = normalized(left), normalized(right)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    a_tokens, b_tokens = set(a.split()), set(b.split())
    union = a_tokens | b_tokens
    jac = len(a_tokens & b_tokens) / len(union) if union else 0.0
    return max(seq, jac)


def strip_discourse_numbers(text: str) -> str:
    """Remove phrases such as "one step" or "two parts" that are not quantities."""
    lowered = text.lower()
    lowered = re.sub(
        r"\b(?:one|two)\s+(?:part|parts|step|steps|sentence|sentences|question|questions|"
        r"change|changes|action|actions|thing|things|way|ways|phrase|phrases)\b",
        "",
        lowered,
    )
    return re.sub(r"\bone at a time\b", "", lowered)


def number_values(text: str) -> set[int]:
    values = {int(value) for value in re.findall(r"(?<!\w)-?\d+(?!\w)", text)}
    # Do not treat discourse phrases such as "one step" or "two parts" as
    # mathematical quantities in the answer-leak validator.
    lowered = strip_discourse_numbers(text)
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", lowered):
            values.add(value)
    return values


def _contains_hidden_answer_disclosure(reply: str, answer: int) -> bool:
    lowered = reply.lower()
    answer_token = rf"(?:{answer}|{next((word for word, value in NUMBER_WORDS.items() if value == answer), '__never__')})"
    patterns = [
        rf"\b(?:the\s+)?(?:answer|result|total|final amount|amount left|number left)\s+(?:is|are|equals|=)\s*{answer_token}\b",
        rf"\b(?:altogether|in all)\s+(?:there\s+)?(?:is|are|you have|you get)?\s*{answer_token}\b",
        rf"\bthere\s+(?:is|are|will be|would be)\s+{answer_token}\b",
        rf"\byou\s+(?:have|had|should have|will have|would have|get|receive|end up with|are left with)\s+{answer_token}\b",
        # "that leaves 3", "leaving 3", "so 3 remain", "3 are left", "makes 3"
        rf"\b(?:leaves?|leaving|left with|makes|gives|comes to|adds up to|equals)\s+(?:you\s+)?{answer_token}\b",
        rf"\b{answer_token}\s+(?:is|are|will be)?\s*(?:left|remaining|remain|in total|altogether)\b",
        rf"\b(?:now|then|so|finally)\s+(?:you|there)\s+(?:have|has|are|is|will have|will be)\s+{answer_token}\b",
        rf"=\s*{answer_token}\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)



def _explicit_uncertainty_acknowledgement(reply: str) -> bool:
    lowered = reply.lower()
    # An acknowledgement is a reassurance word near an uncertainty word, in either
    # order. Matching paraphrases rather than fixed sentences keeps this option from
    # collapsing onto one canned line.
    reassure = r"(?:okay|ok\b|alright|all right|fine|normal|understandable|happens|no worries|don'?t worry|that is fine|that's fine|we can|let us|let's|together)"
    uncertain = r"(?:unsure|not sure|aren'?t sure|are not sure|do not know|don'?t know|confus\w*|tricky|puzzl\w*|stuck|hard to tell)"
    patterns = [
        rf"\b{reassure}\b[^.!?]{{0,60}}\b{uncertain}\b",
        rf"\b{uncertain}\b[^.!?]{{0,60}}\b{reassure}\b",
        r"\b(?:i (?:understand|know|can see|hear)|it (?:sounds|seems|looks) like)\b[^.!?]{0,45}"
        r"\b(?:unsure|not sure|confus\w*|tricky|stuck)\b",
        r"\b(?:one step at a time|step by step|work through (?:it|this) together)\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


# Frames that assert how many objects a collection holds, as opposed to how many
# to move. A movement amount must never be spoken as a collection quantity.
_COLLECTION_FRAMES = (
    r"\b(?:contains?|holds?|has|have|had|shows?|showing)\s+(?:only\s+|just\s+|a total of\s+)?{n}\b",
    r"\bthere\s+(?:is|are|were|will be|would be)\s+(?:only\s+|just\s+)?{n}\b",
    r"\byou\s+(?:have|had|will have|would have|end up with|are left with|get)\s+(?:only\s+|just\s+)?{n}\b",
    r"\b{n}\s+\w*\s*(?:are|is|were)?\s*(?:left|remaining|remain|in total|altogether)\b",
    r"\b(?:collection|basket|group|arrangement|total)\b[^.!?]{{0,24}}\b{n}\b",
    r"\b{n}\b[^.!?]{{0,16}}\b(?:in (?:the|your)\s+(?:collection|basket|group|arrangement))",
)


# Verbs that make a number an instruction to move objects rather than a claim
# about how many there are.
_MOVEMENT_VERBS = (
    r"move|moves|moved|moving|return|returns|returned|returning|add|adds|added|adding|"
    r"put|puts|putting|place|places|placed|placing|take|takes|taking|bring|brings|bringing|"
    r"drag|drags|dragging|remove|removes|removed|removing|give|gives|giving|send|sends|sending|"
    r"share|shares|sharing|need|needs|needed|"
    r"taken|brought|given|sent|chosen|joined|left"
)


def _object_nouns(question: dict[str, Any]) -> set[str]:
    visual = question.get("visual", {}) or {}
    nouns = {
        str(visual.get(key, "")).lower()
        for key in ("object_label", "object_plural", "initial_object_label",
                    "change_object_label", "group_label", "recipient_label")
    }
    nouns |= {"object", "objects", "counter", "counters", "group", "groups", "item", "items"}
    return {n for n in nouns if n}


def _states_answer_as_quantity(reply: str, answer: int, question: dict[str, Any]) -> bool:
    """True when the reply attaches the hidden result to the objects themselves.

    Any phrasing that pairs the answer with the story's objects -- "3 cats",
    "3 of the cats", "3 cats still there" -- asserts how many there are, unless a
    movement verb makes it an instruction ("move 3 more cats"). Checking the
    pairing rather than enumerating sentence shapes closes the natural-language
    variations that a frame list keeps missing.
    """
    word = next((w for w, v in NUMBER_WORDS.items() if v == answer), "__never__")
    token = rf"(?:{answer}|{word})"
    nouns = "|".join(sorted((re.escape(n) for n in _object_nouns(question)), key=len, reverse=True))
    if not nouns:
        return False
    lowered = strip_discourse_numbers(reply)
    pairing = rf"\b{token}\b(?:\s+(?:of\s+the|of|more|other|remaining|extra))?\s+(?:{nouns})\b"
    for match in re.finditer(pairing, lowered):
        prefix = lowered[max(0, match.start() - 44):match.start()]
        if re.search(rf"\b(?:{_MOVEMENT_VERBS})\b[^.!?]{{0,24}}$", prefix):
            continue          # an instruction to move that many objects
        return True
    return False


def _used_as_collection_quantity(reply: str, number: int) -> bool:
    word = next((w for w, v in NUMBER_WORDS.items() if v == number), "__never__")
    token = rf"(?:{number}|{word})"
    lowered = strip_discourse_numbers(reply)
    return any(re.search(frame.format(n=token), lowered) for frame in _COLLECTION_FRAMES)


# Openings that mean the tutor has started telling a story instead of teaching.
_NARRATIVE_COMPLIANCE = (
    r"\bhere(?:'s| is) (?:a|the|my|another) (?:simple |short |little |quick |fun )?"
    r"(?:story|tale|poem|rhyme|joke|adventure)\b",
    r"\bonce upon a time\b",
    r"\bthere (?:was|were|lived) (?:once |a long time ago )?(?:a|an|one) \w+",
    r"\blet me tell you (?:a|the|my) (?:story|tale|poem|joke)\b",
    r"\bi(?:'ll| will) tell you (?:a|the|my) (?:story|tale|poem|joke)\b",
    r"\b(?:in|from) a (?:faraway|magical|distant|enchanted) \w+",
)


def _is_narrative_compliance(reply: str) -> bool:
    """True when the reply has begun telling a story rather than tutoring."""
    lowered = reply.lower()
    return any(re.search(pattern, lowered) for pattern in _NARRATIVE_COMPLIANCE)


# Blocking the answer numeral is not enough on equal-sharing questions: a reply can
# hand over the whole operation ("divide 12 by 3") using only story quantities and
# never speak the result. Detect the complete answer-producing expression itself.
_NUMBER_WORDS_FOR_LEAK = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
}


def _numeral_alternation(value: int) -> str:
    """Match a quantity written as a digit or as a word."""
    word = _NUMBER_WORDS_FOR_LEAK.get(value)
    return f"(?:{value}|{word})" if word else str(value)


def _reveals_equal_sharing_operation(reply: str, question: dict[str, Any]) -> bool:
    if question.get("interaction") != "EQUAL_SHARING":
        return False

    params = question["parameters"]
    total = _numeral_alternation(int(params["total"]))
    recipients = _numeral_alternation(int(params["recipient_count"]))
    lowered = reply.lower()

    divide = r"divid(?:e|es|ed|ing|up)"
    split = r"split(?:s|ting)?"
    share = r"shar(?:e|es|ed|ing)"
    # Natural tutor language often inserts articles and object nouns around the
    # quantities: "divide the 12 pieces among the 3 people". Permit a short,
    # punctuation-free gap so the validator judges the operation, not wording.
    gap = r"[^.!?]{0,28}"
    patterns = [
        rf"\b{divide}\b{gap}\b{total}\b{gap}\bby\b{gap}\b{recipients}\b",
        rf"\b{total}\b{gap}\bdivided\b{gap}\bby\b{gap}\b{recipients}\b",
        rf"\b{total}\s*(?:÷|/)\s*{recipients}\b",
        rf"\b(?:{divide}|{split}|{share})\b{gap}\b{total}\b{gap}\b(?:between|among|into|across|by)\b{gap}\b{recipients}\b",
        rf"\b{total}\b{gap}\b(?:shared|split|divided)\b{gap}\b(?:between|among|into|across|by)\b{gap}\b{recipients}\b",
        rf"\bhow many\b{gap}\beach\b{gap}\b{total}\b{gap}\b{recipients}\b",
        rf"\b{share}\b{gap}\b{total}\b{gap}\bequally\b{gap}\b(?:between|among|across)\b{gap}\b{recipients}\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)



def _reveals_equal_groups_operation(reply: str, question: dict[str, Any]) -> bool:
    """The equal-groups analogue of the equal-sharing leak.

    Only explicit arithmetic is blocked. Restating the story relationship
    ("3 groups of 2", "two flowers each") is what a tutor is supposed to do and
    must stay allowed, so no pattern keys on that phrasing alone.
    """
    if question.get("interaction") != "EQUAL_GROUPS":
        return False

    params = question["parameters"]
    count_value = int(params["group_count"])
    size_value = int(params["group_size"])
    count = _numeral_alternation(count_value)
    size = _numeral_alternation(size_value)
    lowered = reply.lower()

    multiply = r"multipl(?:y|ies|ied|ying)"
    times = r"(?:times|x|\*|×)"
    patterns = [
        rf"\b{multiply}\s+{count}\s+by\s+{size}\b",
        rf"\b{multiply}\s+{size}\s+by\s+{count}\b",
        rf"\b{count}\s*{times}\s*{size}\b",
        rf"\b{size}\s*{times}\s*{count}\b",
        rf"\badd\s+{size}\b[^.!?]{{0,20}}\b{count}\s+times\b",
        rf"\bskip[- ]?count(?:ing)?\s+by\s+{size}\b[^.!?]{{0,20}}\b{count}\s+times\b",
        rf"\bcount(?:ing)?\s+by\s+{size}s?\b[^.!?]{{0,20}}\b{count}\s+times\b",
    ]
    if any(re.search(pattern, lowered) for pattern in patterns):
        return True

    # Repeated addition spelled out: as many terms as there are groups.
    chain = rf"\b{size}\s*\+\s*(?:{size}\s*\+\s*){{{count_value - 2}}}{size}\b" if count_value >= 2 else None
    return bool(chain and re.search(chain, lowered))


def _response_is_grounded(reply: str, question: dict[str, Any]) -> bool:
    lowered = reply.lower()
    visual = question.get("visual", {})
    terms = {
        str(visual.get("object_label", "")).lower(),
        str(visual.get("object_plural", "")).lower(),
        str(visual.get("group_label", "")).lower(),
        str(visual.get("recipient_label", "")).lower(),
        str(visual.get("part_a_label", "")).lower(),
        str(visual.get("part_b_label", "")).lower(),
        "arrangement",
        "collection",
        "object bank",
        "removed area",
        # Region titles the child sees on screen (also used by the VR viewpoint context).
        "removed objects",
        "objects to try",
        "objects to share",
        "bank of objects",
        "group",
        "recipient",
        "ratio",
        "labelled collection",
        "labeled collection",
        "first collection",
        "second collection",
        "story",
    }
    return any(term and term in lowered for term in terms)


def _contradicts_explicit_story_fact(reply: str, question: dict[str, Any]) -> bool:
    """Reject direct negations of quantities explicitly stated in the story.

    This intentionally targets high-confidence contradictions such as
    "you do not need two green apples" when the body explicitly states
    "two green apples". It does not attempt open-ended NLI.
    """
    lowered = reply.lower()
    body = str(question.get("body", "")).lower()
    negation = r"(?:do\s+not|don'?t|does\s+not|doesn'?t|needn'?t|not)\s+(?:really\s+)?need"
    not_required = r"(?:is|are)\s+not\s+(?:actually\s+)?(?:needed|required)"
    if not (re.search(negation, lowered) or re.search(not_required, lowered)):
        return False

    visual = question.get("visual", {}) or {}
    labels = [
        str(visual.get("initial_object_label", "")).lower(),
        str(visual.get("change_object_label", "")).lower(),
        str(visual.get("object_label", "")).lower(),
        str(visual.get("object_plural", "")).lower(),
        str(visual.get("group_label", "")).lower(),
        str(visual.get("recipient_label", "")).lower(),
    ]
    labels = [label for label in labels if label]
    for word, value in NUMBER_WORDS.items():
        tokens = (str(value), word)
        for token in tokens:
            if not re.search(rf"\b{re.escape(token)}\b", body):
                continue
            for label in labels:
                singular = label[:-1] if label.endswith("s") else label
                if not (singular in body or label in body):
                    continue
                fact = rf"\b{re.escape(token)}\b[^.!?]{{0,28}}\b(?:{re.escape(singular)}|{re.escape(label)})s?\b"
                if not re.search(fact, body):
                    continue
                contradiction = (
                    rf"(?:{negation})[^.!?]{{0,25}}\b{re.escape(token)}\b[^.!?]{{0,24}}\b(?:{re.escape(singular)}|{re.escape(label)})s?\b"
                    rf"|\b{re.escape(token)}\b[^.!?]{{0,24}}\b(?:{re.escape(singular)}|{re.escape(label)})s?\b[^.!?]{{0,25}}(?:{not_required})"
                )
                if re.search(contradiction, lowered):
                    return True
    return False


_COMPARE_TERMS = [
    r"\bcompar(?:e|es|ed|ing|ison)\b",
    r"\bmatch(?:es|ed|ing)?\b",
    r"\bsame\b", r"\bdifferent(?:ly)?\b", r"\bdifference\b",
    r"\bequal(?:ly)?\b", r"\buneven\b", r"\bagree(?:s|d)?\b",
    r"\bfit(?:s|ted)?\b", r"\bline up\b", r"\bagainst the story\b",
    r"\bwhat do you notice\b", r"\bnotice\b",
    r"\bmore than\b", r"\bfewer\b", r"\bless than\b",
]
_OBSERVE_TERMS = [
    r"\blook(?:s|ed|ing)?\b(?:\s+\w+){0,2}\s+at\b", r"\blook again\b",
    r"\bcheck(?:s|ed|ing)?\b",
    r"\bcount(?:s|ed|ing)?\b", r"\bsee\b", r"\bshow(?:s|n)?\b",
    r"\bexamine\b", r"\binspect\b", r"\bre-?read\b",
    r"\bhow many\b", r"\bdo all\b", r"\bare any\b", r"\bis the\b",
    r"\bdoes (?:it|that|this|your|each|the)\b", r"\bwhat does\b",
    # completeness and existence questions are observation prompts too
    r"\bis (?:anything|there|everything|it|your|that|this)\b",
    r"\bare (?:there|any|all|they|the|your)\b",
    r"\bfinish(?:ed)?\b", r"\bcomplete(?:d)?\b", r"\bdone\b", r"\bmissing\b",
    r"\bstill waiting\b", r"\bleft over\b",
    # Reporting the current arrangement against the story is check-work too, even
    # when phrased as a statement rather than a question.
    r"\bso far\b", r"\bright now\b", r"\bcurrently\b", r"\bat the moment\b",
    r"\bthe story (?:says|tells|describes|asks)\b",
    r"\byou(?:'|’)?(?:ve| have)? ?(?:moved|added|removed|made|placed|given|put|got|built|shared)\b",
]
_INTERACTION_TERMS = {
    "JOIN": [
        r"\bcollection\b", r"\bbasket\b", r"\bjoin(?:s|ed|ing)?\b",
        r"\badd(?:s|ed|ing)?\b", r"\bmoved (?:in|over|across)\b",
        r"\baltogether\b", r"\btogether\b", r"\bobject bank\b", r"\bbank\b",
        r"\bstill\b", r"\bremain(?:s|ed|ing)?\b", r"\bleft\b",
        r"\bcomplete\b", r"\bfinished\b", r"\bso far\b",
        r"\bwhat you (?:moved|added|placed|put)\b", r"\bstory\b",
    ],
    "REMOVE": [
        r"\bremov(?:e|es|ed|ing|al)\b", r"\btak(?:e|es|en|ing) away\b",
        r"\btook away\b", r"\btaken out\b", r"\btake out\b",
        r"\bmoved out\b", r"\bmoved away\b", r"\bleft\b",
        r"\bremain(?:s|ed|ing)?\b", r"\bstill\b", r"\bgone\b",
        r"\bcollection\b", r"\bbasket\b", r"\bcomplete\b", r"\bso far\b",
        r"\bwhat you (?:moved|removed|took)\b", r"\bstory\b",
    ],
    "EQUAL_GROUPS": [
        r"\bgroup(?:s|ed|ing)?\b", r"\bnumber of groups\b", r"\bgroup count\b",
        r"\bgroup size(?:s)?\b", r"\bin each group\b", r"\bper group\b",
        r"\bin every group\b", r"\bobject bank\b", r"\bbank\b",
        r"\bstill\b", r"\bcomplete\b", r"\bso far\b", r"\bstory\b",
    ],
    "EQUAL_SHARING": [
        r"\bshare(?:s|d|ing)?\b", r"\brecipient(?:s)?\b", r"\bperson\b",
        r"\beach one\b", r"\beveryone\b", r"\bfair(?:ly)?\b",
        r"\bequal(?:ly)?\b", r"\bsame amount\b", r"\bmore\b", r"\bfewer\b",
        r"\bobject bank\b", r"\bbank\b", r"\bundistributed\b",
        r"\bstill\b", r"\bcomplete\b", r"\bso far\b", r"\bstory\b",
    ],
    "PART_TO_PART_RATIO": [
        r"\bratio\b", r"\bfirst (?:part|collection)\b", r"\bsecond (?:part|collection)\b",
        r"\blabel(?:s|led|ed)?\b", r"\border\b", r"\bcompare\b",
        r"\bcollection(?:s)?\b", r"\bpart(?:s)?\b", r"\bstory\b",
    ],
}
# Telling the learner exactly what to move is a hint, not a check.
_CORRECTIVE_ACTION = [
    r"^\s*(?:now\s+|next\s+|first\s+)?(?:please\s+)?(?:move|put|place|add|give|return|take|drag|create|make)\b(?!\s+(?:a|another)\s+(?:look|moment|second|closer look))",
    r"(?:^|[.!?]\s+)(?:now\s+|next\s+|first\s+)?(?:please\s+)?(?:move|put|place|add|give|return|take|drag|create)\s+(?!(?:a|another)\s+(?:look|moment|second|closer)\b)(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+|another|the next|a|an|it)\b",
    r"\byou (?:should|need to|have to|must|can) (?:move|put|place|add|give|return|take|drag|create|make)\b",
    r"\blet(?:'|’)?s (?:move|put|place|add|give|return|drag|create)\b",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _active_mismatch_numbers(question: dict[str, Any], facts: dict[str, Any]) -> set[int]:
    interaction = question.get("interaction")
    active: set[int] = set()
    if interaction == "JOIN":
        active.update(v for v in (facts.get("learner_added_count"), facts.get("expected_added_count")) if isinstance(v, int))
    elif interaction == "REMOVE":
        active.update(v for v in (facts.get("learner_removed_count"), facts.get("expected_removed_count")) if isinstance(v, int))
    elif interaction == "EQUAL_GROUPS":
        active.update(v for v in (facts.get("learner_group_count"), facts.get("expected_group_count"),
                                  facts.get("expected_group_size"), facts.get("undistributed_count")) if isinstance(v, int))
        active.update(v for v in (facts.get("learner_group_sizes") or []) if isinstance(v, int))
    elif interaction == "EQUAL_SHARING":
        active.update(v for v in (facts.get("undistributed_count"), facts.get("expected_recipient_count")) if isinstance(v, int))
        active.update(v for v in (facts.get("learner_share_sizes") or []) if isinstance(v, int))
    elif interaction == "PART_TO_PART_RATIO":
        active.update(v for v in (facts.get("learner_part_a"), facts.get("learner_part_b"),
                                  facts.get("expected_part_a"), facts.get("expected_part_b"),
                                  facts.get("unassigned_a"), facts.get("unassigned_b")) if isinstance(v, int))
    return active


def extract_check_work_features(
    reply: str, question: dict[str, Any], facts: dict[str, Any],
) -> dict[str, bool]:
    """Judge a check-work reply on three independent dimensions."""
    lowered = reply.lower()
    interaction = question.get("interaction")
    visual = question.get("visual", {})
    object_terms = [
        rf"\b{re.escape(str(visual.get(key, '')).lower())}\b"
        for key in ("object_label", "object_plural", "group_label", "recipient_label", "part_a_label", "part_b_label")
        if visual.get(key)
    ]

    asks = _matches_any(_COMPARE_TERMS, lowered) or _matches_any(_OBSERVE_TERMS, lowered)

    relevant = _matches_any(_INTERACTION_TERMS.get(interaction, []), lowered)
    if not relevant and object_terms:
        # naming the objects of this problem also anchors the reply to it
        relevant = _matches_any(object_terms, lowered)
    if not relevant:
        active = _active_mismatch_numbers(question, facts)
        relevant = bool(active and number_values(reply).intersection(active))

    corrective = _matches_any(_CORRECTIVE_ACTION, lowered)

    return {
        "asks_comparison_or_observation": asks,
        "matches_active_interaction": relevant,
        "gives_direct_corrective_action": corrective,
    }


def _check_work_targets_active_mismatch(
    reply: str, question: dict[str, Any], facts: dict[str, Any],
) -> bool:
    """Kept for compatibility; now backed by the structured features."""
    features = extract_check_work_features(reply, question, facts)
    return (
        features["asks_comparison_or_observation"]
        and features["matches_active_interaction"]
        and not features["gives_direct_corrective_action"]
    )


_UNVERIFIED_ANSWER_AUTHORSHIP_PATTERNS = (
    # Direct claims that the child authored a written/numerical answer.
    r"\byou(?:'ve| have)?\s+(?:wrote|written|typed|entered|answered|selected|chose|chosen|recorded|filled in|put down)\b",
    r"\bwhat you(?:'ve| have)?\s+(?:wrote|written|typed|entered|answered|selected|chosen|recorded|put down)\b",
    r"\byour (?:written )?answer (?:is|says|shows|was)\b",
    r"\bthe (?:answer|number|numbers) you(?:'ve| have)?\s+(?:wrote|written|entered|typed|gave|selected|chosen|recorded)\b",
    r"\bthe numbers? you(?:'ve| have)? chosen\b",
    r"\bwhat you(?:'ve| have)? written down\b",
    # The manipulative UI does not support drawing, so this is also fabricated authorship.
    r"\byou(?:'ve| have)?\s+(?:drew|drawn|sketched)\b",
)

_UNVERIFIED_SPEECH_ATTRIBUTION_RE = re.compile(
    r"\byou(?:'ve| have)?\s+(?:said|mentioned|reported|stated|told me)\b",
    re.I,
)


def _invents_learner_answer(
    reply: str,
    facts: dict[str, Any],
    request: Any,
) -> bool:
    """Reject claims that the learner authored input which is not verified.

    Visible arrangement facts remain allowed (for example, "you have two groups").
    Written-answer framing is disallowed whenever the answer field is empty. Speech
    attribution is allowed only when the learner's actual typed message contains a
    number that could support that attribution.
    """
    if facts.get("answer_entered"):
        return False

    lowered = reply.lower()
    if any(re.search(pattern, lowered) for pattern in _UNVERIFIED_ANSWER_AUTHORSHIP_PATTERNS):
        return True

    if _UNVERIFIED_SPEECH_ATTRIBUTION_RE.search(lowered):
        typed_numbers = number_values(request.student_message or "")
        attributed_numbers = number_values(reply)
        if not typed_numbers or not attributed_numbers.issubset(typed_numbers):
            return True

    return False


# On the interface path the model writes ordinary English like "one of the bug
# groups". That "one" is a determiner, not a quantity, but the numeric check
# reads it as one and rejects a correct instruction every time. Strip only these
# fixed non-quantity phrases, and only for INTERFACE_HELP, so that a real
# quantity statement such as "Move 1 flower" is still caught.
# The model writes ordinary English: "dragging", "clicking", "moved". The old
# gate required the bare stem, so a correct interface instruction was rejected
# for grammar alone. This admits only inflections of already-approved words --
# it adds no new vocabulary and touches no answer protection.
# mov(?:e|es|ed|ing) is deliberate: the optional form would match a bare "mov".
INTERFACE_HELP_PATTERN = re.compile(
    r"\b("
    r"drag(?:s|ged|ging)?|"
    r"click(?:s|ed|ing)?|"
    r"select(?:s|ed|ing)?|"
    r"mov(?:e|es|ed|ing)|"
    r"undo|reset|"
    r"object bank|add group|copy group|recipient"
    r")\b",
    re.IGNORECASE,
)


INTERFACE_NON_QUANTITY_PHRASES = (
    "one of the",
    "one of those",
    "one of your",
    "a group",
    "an object",
)


def remove_interface_determiners(text: str) -> str:
    normalized = text.lower()
    for phrase in INTERFACE_NON_QUANTITY_PHRASES:
        normalized = normalized.replace(phrase, " ")
    return normalized


# --- Changes from v4 after the first real-model run ---

# Fix A. v4 accepted only the bare verbs (move, place, check, give, ...), so
# real hints such as "Start by placing the red apples..." or "Start by checking
# your groups..." were rejected as having no action. v4 had already fixed the same
# problem for interface help. Inflections of v4's verbs are accepted, and "choose"
# is added. This rule decides only whether a hint contains an action; it does not
# touch any answer-protection rule.
HINT_ACTION_WORDS = (
    r"\b(?:"
    r"mov(?:e|es|ed|ing)|drag(?:s|ged|ging)?|plac(?:e|es|ed|ing)|count(?:s|ed|ing)?|"
    r"compar(?:e|es|ed|ing)|look(?:s|ed|ing)?|check(?:s|ed|ing)?|mak(?:e|es|ing)|made|"
    r"creat(?:e|es|ed|ing)|giv(?:e|es|en|ing)|gave|shar(?:e|es|ed|ing)|focus(?:es|ed|ing)?|"
    r"notic(?:e|es|ed|ing)|try|tries|tried|trying|tell(?:s|ing)?|told|show(?:s|ed|n|ing)?|"
    r"choos(?:e|es|ing)|chose|chosen|"
    r"pick(?:s|ed|ing)?|point(?:s|ed|ing)?|select(?:s|ed|ing)?|"
    r"tak(?:e|es|en|ing)|took|put(?:s|ting)?|add(?:s|ed|ing)?|remov(?:e|es|ed|ing)|"
    r"find(?:s|ing)?|us(?:e|es|ed|ing)|pull(?:s|ed|ing)?|"
    r"turn(?:s|ed|ing)?"
    r")\b"
)

# v4's original list, still used for the "only one step" check.
V4_HINT_ACTION_WORDS = r"\b(move|drag|place|count|compare|look|check|make|create|give|share|focus|notice|try|tell|show)\b"

_DIGITS = re.compile(r"(?<!\w)-?\d+(?!\w)")
_SMALL_WORDS = {"one": 1, "two": 2}
# Words after "two" that name the two-part structure of a JOIN or RATIO story.
_TWO_PART_NOUNS = r"(?:groups|parts|collections|colors|colours|kinds|amounts|sets)"


def _harmless_small_word(lowered: str, start: int, end: int, word: str,
                         question: dict[str, Any]) -> bool:
    """Is this one occurrence of "one"/"two" an ordinary word, not a quantity?

    Never harmless if it is an exact move: "more" right after it, or a movement
    verb in the 25 characters before it ("move two", "give one more").
    Otherwise harmless only if it is one of:
      - a contrast: "not just one color", "not only one", "not just to one cousin"
      - "one" before a word that is not one of the question's object or region nouns
        ("one color", but not "one apple" or "one cinnamon swirl")
      - "two" naming the two parts of a JOIN or RATIO story ("the two groups compare")
    """
    after = lowered[end:end + 40]
    clause_start = max(lowered.rfind(c, 0, start) for c in ".!?;:,") + 1
    before = lowered[clause_start:start]
    if word == "one" and re.match(r"\s+of\s+(?:the|those|your)\b", after):
        return True
    if re.match(r"\s+more\b", after):
        return False
    if re.search(r"\bnot\s+(?:just|only)(?:\s+(?:to|for|in|with))?\s*$", before):
        return True
    if re.search(rf"\b(?:{_MOVEMENT_VERBS})\b[^.!?]{{0,25}}$", lowered[max(0, start - 40):start]):
        return False
    following = after.lstrip()
    nouns = sorted(_object_nouns(question), key=len, reverse=True)
    names_object = any(re.match(rf"{re.escape(n)}s?\b", following) for n in nouns)
    if word == "one" and re.match(r"[a-z]", following) and not names_object:
        return True
    if word == "two" and question.get("interaction") in {"JOIN", "PART_TO_PART_RATIO"} \
            and re.match(rf"{_TWO_PART_NOUNS}\b", following):
        return True
    return False


def quantity_numbers(text: str, answer: int, question: dict[str, Any]) -> set[int]:
    """Numbers checked against the allowed-number list (restricted Fix B).

    Same as v4 `number_values`, except that "one"/"two" written as words are not
    counted when every occurrence is harmless (`_harmless_small_word`) and the
    value is not the hidden answer. Digits are always counted. Rules that look for
    the answer itself (`hidden_answer_disclosure`, `answer_as_quantity`,
    `hint_states_answer`, `number_in_confirmation`) still use `number_values`.
    """
    values = number_values(text)
    lowered = strip_discourse_numbers(text)
    digits = {int(v) for v in _DIGITS.findall(text)}
    for word, value in _SMALL_WORDS.items():
        if value not in values or value in digits or value == answer:
            continue
        occurrences = list(re.finditer(rf"\b{word}\b", lowered))
        if occurrences and all(_harmless_small_word(lowered, m.start(), m.end(), word, question)
                               for m in occurrences):
            values.discard(value)
    return values


def check_response(
    reply: str,
    question: dict[str, Any],
    request: Any,
    facts: dict[str, Any],
    context: dict[str, Any],
    *,
    check_repetition: bool = True,
) -> Optional[str]:
    """Return None if the reply is safe, else the name of the first rule it breaks."""
    if not reply or len(reply) > 520:
        return "length"

    lowered = reply.lower()
    if any(term in lowered for term in ("misconception", "confidence", "language model", "system prompt")):
        return "internal_terms"
    if re.search(r"\b(?:ask|tell)\s+(?:the\s+)?(?:student|learner|you)\b", lowered):
        return "third_party_instruction"
    if re.search(r"\b(?:the answer|final answer|the total is|altogether there are|so there are)\b", lowered):
        return "answer_phrase"
    if _contradicts_explicit_story_fact(reply, question):
        return "contradicts_story"
    if _invents_learner_answer(reply, facts, request):
        return "invents_learner_answer"

    answer = hidden_answer(question)
    if facts["student_correct"]:
        # A success confirmation should never contain any quantity.
        if number_values(reply):
            return "number_in_confirmation"
    else:
        if _contains_hidden_answer_disclosure(reply, answer):
            return "hidden_answer_disclosure"
        allowed_numbers = {int(value) for value in context.get("allowed_numbers_in_response", [])}
        # Interface guidance names no mathematical quantities, so determiner
        # phrases are cleaned before counting. Every other path is unchanged.
        countable = (remove_interface_determiners(reply)
                     if request.support_type == "INTERFACE_HELP" else reply)
        used_numbers = quantity_numbers(countable, answer, question)
        if not used_numbers.issubset(allowed_numbers):
            return "number_not_allowed"
        # The hidden result may be named as a story quantity or as the number of
        # objects to move, but never as the size of a collection -- that states the
        # answer no matter which role admitted the number.
        if _used_as_collection_quantity(reply, answer) or _states_answer_as_quantity(reply, answer, question):
            return "answer_as_quantity"
        # More generally, a quantity permitted only because it is a movement amount
        # may not be spoken as a collection size either.
        roles = context.get("number_roles", {})
        for number in used_numbers:
            if set(roles.get(str(number), [])) == {"movement"} and _used_as_collection_quantity(reply, number):
                return "movement_as_quantity"

    if not facts["student_correct"]:
        if request.support_type == "INTERFACE_HELP":
            if not INTERFACE_HELP_PATTERN.search(reply):
                return "interface_help_off_topic"
        elif request.support_type == "SMALLER_EXAMPLE":
            example = context.get("smaller_example") or {}
            expected_numbers = {int(example.get("first", -999)), int(example.get("second", -998))}
            if not re.search(r"\b(example|imagine|suppose|try this|smaller)\b", lowered):
                return "example_missing"
            if not expected_numbers.issubset(number_values(reply)):
                return "example_numbers_missing"
        elif request.support_type == "SIMPLIFY_STORY":
            if not re.search(r"\b(story|starts|already|first|then|leaves|joins|each|shared|share|groups)\b", lowered):
                return "story_help_off_topic"
        elif request.support_type == "HINT":
            # A hint must never speak the hidden result, even when that value is
            # currently visible in an incorrect arrangement (especially share size).
            if answer in number_values(reply):
                return "hint_states_answer"
            # ...nor hand over the operation that produces it.
            if _reveals_equal_sharing_operation(reply, question):
                return "hint_sharing_operation"
            if _reveals_equal_groups_operation(reply, question):
                return "hint_groups_operation"
            # A hint request is neutral; it does not require reassurance language.
            # It must remain one grounded, actionable scaffold.
            # Fix A applies only to "is there an action?". The one-step check below
            # keeps v4's exact verb list, so it is not made stricter.
            action_words = V4_HINT_ACTION_WORDS
            if not re.search(HINT_ACTION_WORDS, lowered):
                return "hint_no_action"
            if re.search(r"\b(first|then|next|after that|finally)\b", lowered) and len(re.findall(action_words, lowered)) > 1:
                return "hint_multiple_steps"
            if not _response_is_grounded(reply, question):
                return "hint_not_grounded"
        elif request.support_type == "UNSURE":
            if not _explicit_uncertainty_acknowledgement(reply):
                return "unsure_no_acknowledgement"
        elif request.support_type in {"CHECK_WORK", "AUTO_CHECK"}:
            if not _response_is_grounded(reply, question):
                return "check_not_grounded"
            if request.support_type == "CHECK_WORK":
                # Check-work must not become a second answer channel.
                if question.get("interaction") == "EQUAL_SHARING":
                    if answer in number_values(reply) or _reveals_equal_sharing_operation(reply, question):
                        return "check_sharing_answer"
                if question.get("interaction") == "EQUAL_GROUPS" and _reveals_equal_groups_operation(reply, question):
                    return "check_groups_operation"
                if not _check_work_targets_active_mismatch(reply, question, facts):
                    return "check_not_inspection"
    if request.student_message.strip():
        # A reply to something the learner typed must still be about this question,
        # and must never become the story, poem or joke that was asked for.
        if not _response_is_grounded(reply, question):
            return "message_reply_not_grounded"
        if _is_narrative_compliance(reply):
            return "narrative_compliance"

    if check_repetition:
        recent = [message.content for message in request.conversation_history[-12:] if message.role == "tutor"]
        if any(similarity(reply, old) >= 0.68 for old in recent):
            return "repetition"
    return None



def response_is_safe(reply, question, request, facts, context, *, check_repetition: bool = True) -> bool:
    """v4 interface: True when `check_response` finds no problem."""
    return check_response(reply, question, request, facts, context, check_repetition=check_repetition) is None
