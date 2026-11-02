import json
from pathlib import Path
import pytest
from app.pov_context import build_pov_context, classify_visibility
from app.schemas import ViewData
from app.config import Settings
from app.llm.prompts import build_prompt


def test_visibility_boundaries():
    assert classify_visibility(0.0) == 'not_visible'
    assert classify_visibility(0.10) == 'partially_visible'
    assert classify_visibility(0.70) == 'mostly_visible'
    assert classify_visibility(None) == 'unknown'


def test_region_whitelist_label_history_and_extra_group():
    question = {'interaction': 'EQUAL_GROUPS', 'parameters': {'group_count': 3}, 'visual': {'group_label': 'Basket'}}
    view = ViewData.model_validate({'regions': [
        {'region_id': 'group_1', 'visible_fraction': 1, 'label_visible': False, 'label_seen_this_attempt': True},
        {'region_id': 'group_2', 'visible_fraction': 0, 'label_visible': False, 'label_seen_this_attempt': False},
        {'region_id': 'group_4', 'visible_fraction': 0.5},
        {'region_id': 'group_99', 'visible_fraction': 1},
    ]})
    context, warnings = build_pov_context(question, view, learner_state={'group_sizes': [2, 2, 2, 2]})
    assert context['regions'][0]['region_name'] == 'Basket 1'
    assert context['regions'][0]['learner_has_seen_name'] is True
    assert context['regions'][1]['region_name'] == 'Basket 2'
    assert context['regions'][1]['learner_has_seen_name'] is False
    assert context['regions'][2]['region_name'] == 'Basket 4'
    assert len(context['regions']) == 3
    assert any('group_99' in w for w in warnings)
    assert 'group_4' not in json.dumps(context)


def test_missing_view():
    context, warnings = build_pov_context({'interaction': 'REMOVE', 'parameters': {}}, None)
    assert context is None and warnings


def test_snapshot_fields_survive():
    view = ViewData.model_validate({'snapshot_source': 'best_recent', 'snapshot_age_ms': 450})
    assert view.model_dump()['snapshot_age_ms'] == 450
    assert view.snapshot_source == 'best_recent'


def test_bad_thresholds_fail_on_settings_construction():
    with pytest.raises(ValueError):
        Settings(pov_visibility_low=0.9, pov_visibility_high=0.7)


def test_pov_rules_have_real_newlines():
    import inspect
    import app.llm.prompts as prompts
    source = inspect.getsource(prompts.build_prompt)
    assert 'instructions += "\\n\\n" + POV_RULES' in source
    assert 'instructions += "\\\\n\\\\n" + POV_RULES' not in source
