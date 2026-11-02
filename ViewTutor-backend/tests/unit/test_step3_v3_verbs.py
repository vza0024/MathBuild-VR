"""Action verbs seen in real V2 smoke-run replies that were wrongly blocked as hint_no_action."""
import re
from app.answer_protection import HINT_ACTION_WORDS, V4_HINT_ACTION_WORDS


def has_action(text):
    return re.search(HINT_ACTION_WORDS, text.lower()) is not None


def test_find_and_use_count_as_actions():
    assert has_action("Find 2 counters in the collection to stand for the bedrooms on the second floor.")
    assert has_action("Use the removed objects area to show the bedrooms on the second floor.")
    assert has_action("Pull one counter out of the starting collection.")


def test_non_actions_still_have_no_action():
    assert not has_action("Apples are nice in a basket.")
    assert not has_action("Each building has 3 classrooms.")  # noun, not an action
    assert not has_action("Matthew found 9 big red apples.")  # "found" is a noun-like past form here


def test_one_step_check_keeps_the_original_verb_list():
    assert "find" not in V4_HINT_ACTION_WORDS and "use" not in V4_HINT_ACTION_WORDS


def test_on_screen_region_titles_ground_a_hint():
    from app.answer_protection import _response_is_grounded
    q = {"visual": {"object_label": "counter", "object_plural": "counters"}}
    # No object word and no "collection"/"story": only the region title anchors it.
    assert _response_is_grounded("Look at the removed objects area.", {"visual": {}})
    assert _response_is_grounded("Try the objects to try.", {"visual": {}})
    assert not _response_is_grounded("Apples are nice.", q)


def test_turn_toward_counts_as_an_action():
    # The V2 viewpoint prompt asks the tutor to say this before naming a hidden region.
    assert has_action("Turn toward the joining collection, where the kids from Tuesday belong.")
    assert has_action("Turn toward the apples area to work on that part of the story.")
    assert "turn" not in V4_HINT_ACTION_WORDS   # one-step check unchanged
