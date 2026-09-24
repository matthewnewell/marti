"""Triage: preview is side-effect free, commit re-ranks, logs, and raises hot flags only for
projects that moved up, without duplicating open flags."""

from demo_data import AVIONICS_ID, BRACKET_ID, NACELLE_ID, RADAR_ID
from models import HotFlag, PriorityChange

SEEDED = [RADAR_ID, BRACKET_ID, AVIONICS_ID, NACELLE_ID]
NACELLE_FIRST = [NACELLE_ID, RADAR_ID, BRACKET_ID, AVIONICS_ID]


def test_preview_moves_nacelle_earlier_and_saves_nothing(demo_client):
    d = demo_client.post("/api/triage/preview", json={"order": NACELLE_FIRST}).get_json()
    nac = next(p for p in d["projects"] if p["depot_project_id"] == NACELLE_ID)
    assert nac["rank_delta"] == 3
    assert nac["finish_delta_days"] < 0
    br = next(p for p in d["projects"] if p["depot_project_id"] == BRACKET_ID)
    assert br["finish_delta_days"] >= 0
    assert PriorityChange.query.count() == 1  # only the seeded one


def test_preview_rejects_incomplete_order(demo_client):
    res = demo_client.post("/api/triage/preview", json={"order": [RADAR_ID]})
    assert res.status_code == 400


def test_commit_requires_name_and_reason(demo_client):
    res = demo_client.post("/api/triage/commit", json={"order": NACELLE_FIRST, "changed_by": "Jo"})
    assert res.status_code == 400


def test_commit_reranks_and_flags_only_projects_that_moved_up(demo_client):
    res = demo_client.post("/api/triage/commit", json={
        "order": NACELLE_FIRST, "changed_by": "Jo Smith", "reason": "Customer escalation"})
    assert res.status_code == 200
    d = res.get_json()
    assert [p["depot_project_id"] for p in d["projects"]] == NACELLE_FIRST
    flagged = {f["depot_project_id"] for f in d["hot_flags_raised"]}
    assert flagged == {NACELLE_ID}
    keys = {f["target_key"] for f in d["hot_flags_raised"]}
    assert "NO-2001/30" in keys  # the trim & drill job queued at MACH-5
    assert d["history"][0]["changed_by"] == "Jo Smith"


def test_open_flags_are_not_duplicated(demo_client):
    demo_client.post("/api/triage/commit", json={
        "order": NACELLE_FIRST, "changed_by": "Jo", "reason": "r1"})
    demo_client.post("/api/triage/commit", json={"order": SEEDED, "changed_by": "Jo", "reason": "r2"})
    demo_client.post("/api/triage/commit", json={
        "order": NACELLE_FIRST, "changed_by": "Jo", "reason": "r3"})
    keys = [f.target_key for f in HotFlag.query.filter_by(depot_project_id=NACELLE_ID)]
    assert len(keys) == len(set(keys))


def test_acknowledge_then_resolve(demo_client):
    d = demo_client.post("/api/triage/commit", json={
        "order": NACELLE_FIRST, "changed_by": "Jo", "reason": "r"}).get_json()
    fid = d["hot_flags_raised"][0]["id"]
    assert demo_client.post(f"/api/hot-flags/{fid}/acknowledge", json={"name": ""}).status_code == 400
    ack = demo_client.post(f"/api/hot-flags/{fid}/acknowledge", json={"name": "Pat"}).get_json()
    assert ack["status"] == "acknowledged" and ack["acknowledged_by"] == "Pat"
    assert demo_client.post(f"/api/hot-flags/{fid}/resolve").get_json()["status"] == "resolved"


def test_need_by_update_changes_impact(demo_client):
    d = demo_client.put(f"/api/triage/{NACELLE_ID}/need-by", json={"need_by": "2030-01-01"}).get_json()
    nac = next(p for p in d["projects"] if p["depot_project_id"] == NACELLE_ID)
    assert nac["forecast"]["status"] == "on_track"
