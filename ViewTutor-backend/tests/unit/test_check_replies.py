"""The automatic reply checker catches the known problems and passes good replies."""
from __future__ import annotations

import pytest

from app.questions import QUESTION_BY_ID, QUESTIONS
from scripts.check_replies import check_reply

JOIN = QUESTION_BY_ID["MC-JOIN-nluds-0001"]       # 7 red + 2 green, answer 9
RATIO = next(q for q in QUESTIONS if q["interaction"] == "PART_TO_PART_RATIO")


def log(text, status="generated", construction="incomplete"):
    return {"status": status, "final_text": text, "construction_status": construction}


@pytest.mark.parametrize("question, state, text, flag", [
    (JOIN, {"added_count": 0, "current_count": 7}, "Start by placing seven red apples in the Basket.",
     "asks_to_place_present"),
    (RATIO, {"part_a_count": 5, "part_b_count": 0, "unassigned_a": 0, "unassigned_b": 6},
     "The boys are already in their group. Try making a group for the girls next.", "asks_to_create_existing"),
    (JOIN, {"added_count": 0, "current_count": 7}, "There are 9 apples in the basket.", "answer_leak"),
    (JOIN, {"added_count": 0, "current_count": 7}, "Move 2 more apples into the basket.", "exact_move"),
    (JOIN, {"added_count": 0, "current_count": 7, "part_a_count": 7, "part_b_count": 0},
     "The red apples are missing from the Basket.", "claims_missing"),
    (JOIN, {"added_count": 1, "current_count": 8}, "Your Basket has more apples than the story describes.",
     "claims_too_many"),
])
def test_known_problems_are_flagged(question, state, text, flag):
    assert flag in check_reply(question, state, log(text))


@pytest.mark.parametrize("question, state, text", [
    (JOIN, {"added_count": 0, "current_count": 7, "part_a_count": 7, "part_b_count": 0},
     "The red apples are in the Basket, but the green apples are missing."),
    (JOIN, {"added_count": 0, "current_count": 7}, "Check whether the Basket shows both the red and the green apples."),
    (JOIN, {"added_count": 3, "current_count": 10},
     "Your Basket has more apples than the story describes. Check the green apples."),
    (RATIO, {"part_a_count": 0, "part_b_count": 0, "unassigned_a": 5, "unassigned_b": 6},
     "Start by placing the boys in the boys group."),
])
def test_good_replies_pass(question, state, text):
    construction = "incorrect" if state.get("current_count", 0) > 9 else "incomplete"
    assert check_reply(question, state, log(text, construction=construction)) == []


def test_confirmations_are_not_checked():
    assert check_reply(JOIN, {"added_count": 2, "current_count": 9}, log("Nice work, 2 more!", "confirmed_correct")) == []
