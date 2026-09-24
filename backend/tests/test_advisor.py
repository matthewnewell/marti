"""MARTI's suggestions, capacity levers, proposals, the assembly tree and the AI stub."""

from datetime import date, datetime, timedelta

import scheduler
from db import db
from demo_data import AVIONICS_ID, BRACKET_ID, NACELLE_ID, RADAR_ID
from models import MaterialMaster, Operation, ProductionOrder, Proposal, WorkCenter

SEEDED = [RADAR_ID, BRACKET_ID, AVIONICS_ID, NACELLE_ID]
MON = date(2026, 9, 21)
NOW = datetime(2026, 9, 21, 8, 0)


# --- levers, on hand-built data ---------------------------------------------------------------


def _one_job(app, hours=16, cap=8):
    db.session.add(WorkCenter(code="MILL", description="Mill", capacity_hours_per_day=cap))
    db.session.add(WorkCenter(code="SPARE", description="Spare", capacity_hours_per_day=8))
    db.session.add(MaterialMaster(material_number="OUT-A", description="A", procurement_type="E"))
    o = ProductionOrder(order_number="A1", depot_project_id="A", material_number="OUT-A", quantity=1,
                        released_at=NOW - timedelta(hours=1))
    db.session.add(o)
    db.session.flush()
    db.session.add(Operation(order_id=o.id, seq=10, description="mill", work_center="MILL", run_hours_per_unit=hours))
    db.session.commit()
    return scheduler.Snapshot.load()


def _finish(snap, levers=None):
    return scheduler.forecast(snap, ["A"], {}, MON, NOW, levers=levers)["projects"]["A"]["projected_finish"]


def test_add_hours_shortens_the_job(app):
    snap = _one_job(app)
    assert _finish(snap) == "2026-09-22"
    assert _finish(snap, [{"type": "add_hours", "work_center": "MILL", "hours_per_day": 8}]) == "2026-09-21"


def test_add_hours_respects_start_date(app):
    snap = _one_job(app, hours=24)
    late = [{"type": "add_equipment", "work_center": "MILL", "hours_per_day": 8, "start_date": "2026-09-23"}]
    assert _finish(snap) == "2026-09-23"
    assert _finish(snap, late) == "2026-09-23"  # extra capacity arrives the day it would finish anyway


def test_move_labor_takes_capacity_away(app):
    snap = _one_job(app)
    moved = [{"type": "move_labor", "from_work_center": "MILL", "to_work_center": "SPARE", "hours_per_day": 4}]
    assert _finish(snap, moved) == "2026-09-24"  # 16 h at 4 h/day


def test_outsource_uses_vendor_turnaround_not_capacity(app):
    snap = _one_job(app, hours=80)
    out = [{"type": "outsource", "order_number": "A1", "seq": 10, "turnaround_days": 3}]
    assert _finish(snap, out) == "2026-09-23"


# --- demo-backed routes -----------------------------------------------------------------------


def test_suggestions_find_a_ranking_with_fewer_late_projects(demo_client):
    d = demo_client.get("/api/triage/suggestions").get_json()
    assert d["rankings"], "the demo is built so a better ranking exists"
    best = d["rankings"][0]
    assert best["source"] == "engine"
    assert best["summary"]["late_days_after"] < best["summary"]["late_days_before"]
    assert {c["depot_project_id"] for c in d["cut_in"]} == set(SEEDED[1:])


def test_commit_records_where_the_ranking_came_from(demo_client):
    best = demo_client.get("/api/triage/suggestions").get_json()["rankings"][0]
    d = demo_client.post("/api/triage/commit", json={
        "order": best["ranking"], "changed_by": "Jo", "reason": "Engine suggestion", "source": "engine"}).get_json()
    assert d["history"][0]["source"] == "engine"


def test_ai_proposal_commits_through_triage(demo_client):
    p = demo_client.post("/api/proposals", json={
        "kind": "rerank", "source": "ai", "title": "Nacelle first", "ranking": [NACELLE_ID, RADAR_ID, BRACKET_ID, AVIONICS_ID],
    }).get_json()
    shown = demo_client.get("/api/triage/suggestions").get_json()["proposals"]
    assert shown[0]["id"] == p["id"] and shown[0]["impact"]
    d = demo_client.post("/api/triage/commit", json={
        "order": p["ranking"], "changed_by": "Jo", "reason": "AI suggestion", "proposal_id": p["id"]}).get_json()
    assert d["history"][0]["source"] == "ai"
    assert db.session.get(Proposal, p["id"]).status == "committed"


def test_scenario_third_shift_recovers_nacelle(demo_client):
    d = demo_client.post("/api/constraints/scenario", json={
        "levers": [{"type": "add_hours", "work_center": "MACH-5", "hours_per_day": 8}]}).get_json()
    assert NACELLE_ID in d["summary"]["recovered"]


def test_scenario_rejects_bad_levers(demo_client):
    assert demo_client.post("/api/constraints/scenario", json={"levers": [{"type": "magic"}]}).status_code == 400
    assert demo_client.post("/api/constraints/scenario", json={
        "levers": [{"type": "add_hours", "work_center": "NOPE", "hours_per_day": 8}]}).status_code == 400


def test_capacity_proposal_accept_needs_a_name(demo_client):
    p = demo_client.post("/api/proposals", json={
        "kind": "capacity", "title": "Third shift on MACH-5",
        "levers": [{"type": "add_hours", "work_center": "MACH-5", "hours_per_day": 8}]}).get_json()
    assert demo_client.post(f"/api/proposals/{p['id']}/accept", json={}).status_code == 400
    assert demo_client.post(f"/api/proposals/{p['id']}/accept", json={"name": "Pat"}).get_json()["status"] == "accepted"


def test_routing_tree_nests_three_levels(demo_client):
    d = demo_client.get(f"/api/routing?project_id={RADAR_ID}").get_json()
    (root,) = d["projects"][0]["tree"]
    assert root["order_number"] == "RO-1000" and root["critical"]
    cover = next(k for k in root["children"] if k["order_number"] == "RO-1002")
    assert {k["order_number"] for k in cover["children"]} == {"RO-1003", "RO-1004"}
    assert root["rollup"]["orders"] == 5


def test_acquisition_view_covers_all_projects_or_one(demo_client):
    everything = demo_client.get("/api/acquisition").get_json()["lines"]
    radar = demo_client.get(f"/api/acquisition?project_id={RADAR_ID}").get_json()["lines"]
    assert {l["depot_project_id"] for l in radar} == {RADAR_ID}
    assert len(everything) > len(radar)


def test_ai_stub_says_not_connected(demo_client):
    d = demo_client.post("/api/ai/triage-suggestions", json={"goals": "Radar can't slip"}).get_json()
    assert d["status"] == "not_connected" and d["proposals"] == []


# --- round 3: journal, issues, expedite ------------------------------------------------------


def test_commit_journals_each_changed_project_as_the_committer(demo_client, app):
    demo_client.post("/api/triage/commit", json={
        "order": [NACELLE_ID, RADAR_ID, BRACKET_ID, AVIONICS_ID], "changed_by": "Jordan Park",
        "person_id": "person-jordan", "reason": "Customer escalation"})
    by_project = {pid: body for pid, _, body in app.journal}
    assert {pid for pid, person, _ in app.journal} >= {NACELLE_ID, RADAR_ID}
    assert all(person == "person-jordan" for _, person, _ in app.journal)
    assert "moved from #4 to #1" in by_project[NACELLE_ID]
    assert "Customer escalation" in by_project[NACELLE_ID]


def test_issues_say_who_fixes_what(demo_client):
    rows = {p["depot_project_id"]: p for p in demo_client.get("/api/triage").get_json()["projects"]}
    avionics = rows[AVIONICS_ID]["issues"]
    kinds = {i["kind"] for i in avionics}
    assert {"short", "held"} <= kinds
    pr = next(i for i in avionics if i["material_number"] == "7710-0450")
    assert pr["owner"] == "PR approver" and "Release PR" in pr["action"]
    held = next(i for i in avionics if i["kind"] == "held")
    assert held["link"] == "routing" and held["focus"] == "AO-4002"


def test_expedite_material_lever_moves_the_finish(demo_client):
    base = demo_client.get("/api/triage").get_json()["projects"]
    radar = next(p for p in base if p["depot_project_id"] == RADAR_ID)["forecast"]["projected_finish"]
    soon = (date.today() + timedelta(days=1)).isoformat()
    d = demo_client.post("/api/constraints/scenario", json={"levers": [
        {"type": "expedite_material", "material_number": "5310-7010", "ready_date": soon}]}).get_json()
    after = next(p for p in d["projects"] if p["depot_project_id"] == RADAR_ID)["proposed"]["projected_finish"]
    assert after < radar


def test_people_passthrough(demo_client, monkeypatch):
    import depot_client
    monkeypatch.setattr(depot_client, "fetch_people", lambda: [{"id": "p1", "name": "Jordan Park"}])
    d = demo_client.get("/api/people").get_json()
    assert d["depot_reachable"] and d["people"][0]["name"] == "Jordan Park"
