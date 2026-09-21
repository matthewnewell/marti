"""Route-level tests for MARTI's project routes — real DB (in-memory SQLite), Flask test
client, and a monkeypatched depot_client so these never depend on a live Conway's Depot
(deterministic, same isolation Conway's Depot's own tests use for its DB, applied here to the
network boundary too since MARTI's whole project list depends on it)."""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask

import depot_client
from db import db
from routes.projects import bp as projects_bp
from routes.summary import bp as summary_bp

PROJECT_A = "proj-a"
PROJECT_B = "proj-b"
PROJECT_C = "proj-c"

_DEPOT_PROJECTS = [
    {"id": PROJECT_A, "name": "Has manufacturing flag", "has_manufacturing": True},
    {"id": PROJECT_B, "name": "No flag, in-house material", "has_manufacturing": None},
    {"id": PROJECT_C, "name": "Purchased material only", "has_manufacturing": False},
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(depot_client, "fetch_projects", lambda: _DEPOT_PROJECTS)
    monkeypatch.setattr(
        depot_client, "fetch_project",
        lambda pid: next((p for p in _DEPOT_PROJECTS if p["id"] == pid), None),
    )

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    db.init_app(app)
    app.register_blueprint(projects_bp)
    app.register_blueprint(summary_bp)
    with app.app_context():
        db.create_all()
    with app.test_client() as c:
        yield c


def _add_material(client_app, depot_project_id, procurement_type):
    from models import Material

    with client_app.application.app_context():
        m = Material(depot_project_id=depot_project_id, material_number="M-1", procurement_type=procurement_type)
        db.session.add(m)
        db.session.commit()


def test_project_with_depot_flag_is_included(client):
    projects = client.get("/api/projects").get_json()["projects"]
    ids = {p["depot_project_id"] for p in projects}
    assert PROJECT_A in ids


def test_project_with_in_house_material_is_included(client):
    _add_material(client, PROJECT_B, "E")
    projects = client.get("/api/projects").get_json()["projects"]
    ids = {p["depot_project_id"] for p in projects}
    assert PROJECT_B in ids


def test_project_with_only_purchased_material_is_excluded(client):
    _add_material(client, PROJECT_C, "F")
    projects = client.get("/api/projects").get_json()["projects"]
    ids = {p["depot_project_id"] for p in projects}
    assert PROJECT_C not in ids


def test_tradeoff_upsert_creates_then_updates(client):
    res = client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "high"})
    assert res.status_code == 200
    assert res.get_json()["priority"] == "high"

    res = client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "low"})
    assert res.get_json()["priority"] == "low"


def test_tradeoff_rejects_invalid_priority(client):
    res = client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "urgent"})
    assert res.status_code == 400


def test_impact_flags_low_priority_with_near_due_date(client):
    due = (date.today() + timedelta(days=5)).isoformat()
    res = client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "low", "due_date": due})
    impact = res.get_json()["impact"]
    assert impact["flagged"] is True


def test_impact_not_flagged_for_high_priority_even_when_due_soon(client):
    due = (date.today() + timedelta(days=1)).isoformat()
    res = client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "high", "due_date": due})
    impact = res.get_json()["impact"]
    assert impact["flagged"] is False


def test_impact_not_flagged_with_no_due_date(client):
    res = client.put(f"/api/projects/{PROJECT_A}/tradeoff", json={"priority": "low"})
    impact = res.get_json()["impact"]
    assert impact["flagged"] is False
