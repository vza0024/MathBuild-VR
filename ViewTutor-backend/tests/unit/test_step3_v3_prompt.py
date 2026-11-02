"""Offline checks for the step3-pov-v3 prompt version."""
from app.llm.prompts import POV_RULES_V3, PROMPT_VERSIONS, V3_QUALITY_RULES


def test_v3_registered_and_distinct():
    assert "step3-pov-v3" in PROMPT_VERSIONS
    assert "quotation marks" in V3_QUALITY_RULES
    assert "Never turn the learner without giving that question" in POV_RULES_V3


def test_rule_requires_an_action_word_in_hints():
    assert "action word" in V3_QUALITY_RULES
    assert "only a question" in V3_QUALITY_RULES


def test_v4_prompt_registered_and_rotating_opening():
    from app.llm.prompts import OPENING_VERBS, POV_RULES_V4, V4_STYLE_RULES
    assert "step3-pov-v4" in PROMPT_VERSIONS
    assert "MUST start with" in POV_RULES_V4
    assert "{opening}" in V4_STYLE_RULES
    assert len(set(OPENING_VERBS)) == len(OPENING_VERBS) >= 6


def test_v5_prompt_registered_without_rotating_opening():
    from app.llm.prompts import V5_STYLE_RULES
    assert "step3-pov-v5" in PROMPT_VERSIONS
    assert "at most two short sentences" in V5_STYLE_RULES
    assert "{opening}" not in V5_STYLE_RULES
