"""Route-level tests against the full demo dataset and a monkeypatched Depot (see conftest.py)."""

from demo_data import AVIONICS_ID, BRACKET_ID, NACELLE_ID, RADAR_ID


def test_list_includes_manufacturing_projects_in_rank_order(demo_client):
    d = demo_client.get("/api/projects").get_json()
    ids = [p["depot_project_id"] for p in d["projects"]]
    assert ids == [RADAR_ID, BRACKET_ID, AVIONICS_ID, NACELLE_ID]
    assert "no-mfg" not in ids


def test_avionics_is_blocked_by_unreleased_pr(demo_client):
    d = demo_client.get(f"/api/projects/{AVIONICS_ID}").get_json()
    assert d["forecast"]["status"] == "blocked"
    stages = {l["material_number"]: l["stage"] for l in d["acquisition"]}
    assert stages["7710-0450"] == "pr_created"
    assert stages["7710-0460"] == "no_master"
    held = [o for o in d["orders"] if o["clear_to_build"]["status"] == "held"]
    assert [o["order_number"] for o in held] == ["AO-4002"]


def test_project_detail_shows_routing_position_and_quality(demo_client):
    d = demo_client.get(f"/api/projects/{BRACKET_ID}").get_json()
    bo = next(o for o in d["orders"] if o["order_number"] == "BO-3001")
    assert bo["current_seq"] == 20
    weld = next(op for op in bo["operations"] if op["seq"] == 20)
    assert weld["state"] == "in_process"
    assert weld["quality"][0]["designator"] == "rework"
    assert weld["dwell_hours"] > 0


def test_unknown_project_404(demo_client):
    assert demo_client.get("/api/projects/no-mfg").status_code == 404


def test_constraints_rank_mach5_as_biggest_backlog(demo_client):
    d = demo_client.get("/api/constraints").get_json()
    assert d["work_centers"][0]["code"] == "MACH-5"
    assert any(b["material_number"] == "7710-0450" for b in d["material_blockers"])
