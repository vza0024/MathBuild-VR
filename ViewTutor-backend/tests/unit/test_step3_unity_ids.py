"""Region IDs Unity actually generates (WorkspacePovDebug.GetStableRegionId)."""
import json
from app.pov_context import build_pov_context
from app.schemas import ViewData


def _view(*ids):
    return ViewData.model_validate({"regions": [
        {"region_id": i, "visible_fraction": 0.5, "label_visible": True, "label_seen_this_attempt": True}
        for i in ids]})


def _names(question, ids, **kw):
    context, warnings = build_pov_context(question, _view(*ids), **kw)
    return ([r["region_name"] for r in context["regions"]] if context else []), warnings


JOIN = {"interaction": "JOIN", "parameters": {"initial": 3, "change": 2}, "visual": {}}
SHARING = {"interaction": "EQUAL_SHARING", "parameters": {"recipient_count": 2, "total": 6}, "visual": {}}
RATIO = {"interaction": "PART_TO_PART_RATIO", "parameters": {"part_a": 2, "part_b": 3},
         "visual": {"part_a_label": "red", "part_b_label": "blue"}}
GROUPS = {"interaction": "EQUAL_GROUPS", "parameters": {"group_count": 2, "group_size": 3}, "visual": {}}


def test_join_accepts_all_three_unity_layouts_without_learner_hints():
    for ids in (["destination"], ["part_a", "part_b"], ["part_a", "bank"]):
        names, warnings = _names(JOIN, ids, learner_state={})
        assert len(names) == len(ids) and not warnings, ids


def test_join_bank_has_generic_child_facing_name():
    names, _ = _names(JOIN, ["bank"])
    assert names == ["the objects to try"]


def test_sharing_bank_recognized_next_to_recipients():
    names, warnings = _names(SHARING, ["recipient_1", "recipient_2", "bank"])
    assert len(names) == 3 and not warnings
    assert names[2] == "the objects to share"


def test_ratio_banks_recognized():
    names, warnings = _names(RATIO, ["part_a", "part_b", "bank_a", "bank_b"])
    assert names == ["red", "blue", "the first bank of objects", "the second bank of objects"]
    assert not warnings


def test_bank_ids_still_unknown_where_unity_never_sends_them():
    for question in (GROUPS,):
        names, warnings = _names(question, ["group_1", "bank"])
        assert len(names) == 1 and any("bank" in w for w in warnings)


def test_unknown_ids_still_never_forwarded():
    context, warnings = build_pov_context(JOIN, _view("part_a", "tray"))
    assert "tray" not in json.dumps(context) and any("tray" in w for w in warnings)


def test_join_uses_titles_the_child_sees_when_unity_sends_them():
    names, _ = _names(JOIN, ["part_a", "part_b"], learner_state={
        "workspace_mode": "two_destinations", "part_a_label": "Janet", "part_b_label": "Sharon"})
    assert names == ["Janet", "Sharon"]
    names, _ = _names(JOIN, ["destination"], learner_state={
        "workspace_mode": "single_destination_two_sources", "destination_label": "Basket",
        "part_a_label": "red plum", "part_b_label": "green plum"})
    assert names == ["Basket"]


def test_join_object_labels_never_become_region_names():
    # In single-destination mode part_a_label is an object name, not a region title.
    names, _ = _names(JOIN, ["part_a"], learner_state={
        "workspace_mode": "single_destination_two_sources", "part_a_label": "red plum"})
    assert names == ["the starting collection"]


def test_join_titles_ignored_when_not_plain_short_text():
    names, _ = _names(JOIN, ["destination"], learner_state={"destination_label": "x" * 80})
    assert names == ["the collection"]


def test_real_unity_editor_captures_are_fully_recognized():
    """Three real Editor requests (one per JOIN layout), captured 2026-10-26."""
    from pathlib import Path
    from app.questions import QUESTION_BY_ID
    folder = Path(__file__).resolve().parents[1] / "fixtures" / "unity_captures"
    files = sorted(folder.glob("*.json"))
    assert len(files) == 3
    for path in files:
        body = json.loads(path.read_text(encoding="utf-8"))
        view = ViewData.model_validate(body["view"])
        assert view.snapshot_source in {"current", "recent_best"} and view.snapshot_age_ms is not None
        context, warnings = build_pov_context(
            QUESTION_BY_ID[body["question_id"]], view, learner_state=body["learner_state"])
        assert not warnings, (path.name, warnings)
        assert len(context["regions"]) == len(view.regions), path.name
