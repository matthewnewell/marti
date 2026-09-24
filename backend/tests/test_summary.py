from demo_data import AVIONICS_ID, RADAR_ID


def test_summary_unknown_project_is_quiet(demo_client):
    d = demo_client.get("/api/summary?project_id=unknown-project").get_json()
    assert d["headline"] is None


def test_summary_blocked_project_warns(demo_client):
    d = demo_client.get(f"/api/summary?project_id={AVIONICS_ID}").get_json()
    assert d["headline"] == "Blocked"
    assert d["status"] == "warn"


def test_summary_shows_slack_days(demo_client):
    d = demo_client.get(f"/api/summary?project_id={RADAR_ID}").get_json()
    assert d["headline"].endswith("d")


def test_portfolio_summary_counts_trouble(demo_client):
    d = demo_client.get("/api/summary").get_json()
    assert int(d["headline"]) >= 1
