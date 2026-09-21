import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_projects import *  # noqa: F401,F403  (reuse the client fixture + PROJECT_A)
from test_projects import PROJECT_A


def test_summary_without_data_is_quiet(client):
    d = client.get("/api/summary?project_id=unknown-project").get_json()
    assert d["headline"] is None


def test_summary_with_tradeoff_flags_impact(client):
    from datetime import date, timedelta

    due = (date.today() + timedelta(days=3)).isoformat()
    client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "low", "due_date": due})
    d = client.get(f"/api/summary?project_id={PROJECT_A}").get_json()
    assert d["status"] == "warn"
    assert d["headline"] is not None


def test_portfolio_summary_counts_flagged(client):
    d = client.get("/api/summary").get_json()
    assert d["headline"].isdigit()
