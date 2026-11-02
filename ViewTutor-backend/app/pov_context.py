"""Validated, child-facing VR visibility context. No mathematical judgments."""
from __future__ import annotations

from typing import Any, Mapping
from app.schemas import ViewData
from app.strategies import region_name


# Child-facing names for the banks of not-yet-placed objects. Deliberately generic:
# Unity titles these regions with story-specific text we do not receive.
BANK_NAMES = {
    "JOIN": "the objects to try",
    "EQUAL_SHARING": "the objects to share",
    "RATIO_A": "the first bank of objects",
    "RATIO_B": "the second bank of objects",
}


def _title(value: Any) -> str | None:
    """A region title Unity reports, if it is short plain text."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text if 0 < len(text) <= 40 else None


def classify_visibility(fraction: float | None, low: float = 0.10, high: float = 0.70) -> str:
    if not (0 <= low < high <= 1):
        raise ValueError("visibility thresholds must satisfy 0 <= low < high <= 1")
    if fraction is None:
        return "unknown"
    if fraction < low:
        return "not_visible"
    if fraction < high:
        return "partially_visible"
    return "mostly_visible"


def _region_names(question: Mapping[str, Any], learner_state: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Allowed region IDs according to question type, not learner-reported counts."""
    kind = question["interaction"]
    p = question["parameters"]
    visual = question.get("visual") or {}
    learner_state = learner_state or {}
    if kind == "EQUAL_GROUPS":
        names = {f"group_{i+1}": region_name(dict(question), "group", i)
                 for i in range(max(int(p["group_count"]), len(learner_state.get("group_sizes") or [])))}
    elif kind == "EQUAL_SHARING":
        names = {f"recipient_{i+1}": region_name(dict(question), "recipient", i)
                 for i in range(max(int(p["recipient_count"]), len(learner_state.get("share_sizes") or [])))}
        names["bank"] = BANK_NAMES["EQUAL_SHARING"]
    elif kind == "JOIN":
        # Unity has three JOIN layouts: one destination ("destination"), two target
        # parts ("part_a"/"part_b"), and a starting collection ("part_a") beside an
        # available-objects bank ("bank"). Because the layout is not in the request,
        # every JOIN ID is accepted; an ID that is not on screen is simply never sent.
        # Names are conservative descriptions, not object labels such as "red apple".
        # When Unity sends the titles the child actually sees on the regions
        # (Basket, Janet, Sharon), use those; otherwise the conservative defaults.
        names = {
            "destination": _title(learner_state.get("destination_label")) or "the collection",
            "part_a": "the starting collection",
            "part_b": "the joining collection",
            "bank": BANK_NAMES["JOIN"],
        }
        if learner_state.get("workspace_mode") == "two_destinations":
            names["part_a"] = _title(learner_state.get("part_a_label")) or names["part_a"]
            names["part_b"] = _title(learner_state.get("part_b_label")) or names["part_b"]
    elif kind == "REMOVE":
        names = {"start": "the starting collection", "removed": "the removed objects area"}
    elif kind == "PART_TO_PART_RATIO":
        names = {
            "part_a": str(visual.get("part_a_label") or "the first part"),
            "part_b": str(visual.get("part_b_label") or "the second part"),
            "bank_a": BANK_NAMES["RATIO_A"],
            "bank_b": BANK_NAMES["RATIO_B"],
        }
    else:
        names = {}
    return names


def build_pov_context(
    question: Mapping[str, Any],
    view: ViewData | None,
    *,
    low: float = 0.10,
    high: float = 0.70,
    learner_state: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (safe model context, warnings). Never forward unrecognized IDs."""
    if view is None or not view.regions:
        return None, ["missing_pov_regions"]
    allowed = _region_names(question, learner_state)
    regions = []
    warnings = []
    seen = set()
    for region in view.regions:
        rid = region.region_id
        if not rid or rid not in allowed:
            warnings.append(f"unknown_region_id:{rid!r}")
            continue
        if rid in seen:
            warnings.append(f"duplicate_region_id:{rid}")
            continue
        seen.add(rid)
        visibility = classify_visibility(region.visible_fraction, low, high)
        # Labels are safe to name only if previously seen or visible right now.
        knows_label = region.label_seen_this_attempt is True or region.label_visible is True
        item = {
            "visibility": visibility,
            "label_visible_now": region.label_visible,
            "label_seen_this_attempt": region.label_seen_this_attempt,
        }
        item["region_name"] = allowed[rid]
        item["learner_has_seen_name"] = knows_label
        regions.append(item)
    if not regions:
        return None, warnings + ["no_valid_pov_regions"]
    return {"regions": regions}, warnings
