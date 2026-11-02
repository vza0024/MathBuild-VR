"""Offline regression checks for the Version 2 changes."""
import re

from app.answer_protection import HINT_ACTION_WORDS, quantity_numbers
from app.fallback import _visibility_safe
from app.llm.prompts import POV_RULES, POV_RULES_V2, PROMPT_VERSIONS


def test_new_action_verbs_and_inflections():
    for verb in ("pick", "picked", "picking", "point", "pointing", "select", "selected",
                 "take", "taking", "put", "putting", "add", "adding", "remove", "removing"):
        assert re.search(HINT_ACTION_WORDS, verb), verb


def test_one_of_the_is_not_counted_as_quantity():
    question = {"interaction": "PART_TO_PART_RATIO", "visual": {}, "parameters": {}}
    assert 1 not in quantity_numbers("Try placing one of the monkeys in the collection.", 8, question)
    assert 1 in quantity_numbers("Add one more monkey.", 8, question)
    assert 1 in quantity_numbers("Move 1 monkey.", 8, question)


def test_hidden_removed_area_reorients_without_visibility_claim():
    ctx = {"regions": [{"region_name": "the removed objects area", "visibility": "not_visible",
                        "learner_has_seen_name": True}]}
    original = "Focus on the objects that leave. Look at the removed area and make a small change."
    changed = _visibility_safe(original, ctx)
    assert "Turn toward the removed area" in changed
    assert "Look at the removed area" not in changed
    assert _visibility_safe(original, None) == original


def test_unseen_region_does_not_presume_known_label():
    ctx = {"regions": [{"region_name": "the removed objects area", "visibility": "not_visible",
                        "learner_has_seen_name": False}]}
    assert "Turn to find the area for this part of the story" in _visibility_safe(
        "Look at the removed area.", ctx)


def test_partial_region_and_visible_region():
    text = "Look at the removed area."
    region = {"region_name": "the removed objects area", "learner_has_seen_name": True}
    assert "Adjust your view" in _visibility_safe(text, {"regions": [{**region, "visibility": "partially_visible"}]})
    assert _visibility_safe(text, {"regions": [{**region, "visibility": "mostly_visible"}]}) == text


def test_prompt_is_separately_versioned():
    assert "step3-pov-v2" in PROMPT_VERSIONS
    assert POV_RULES != POV_RULES_V2
