import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask

import depot_client
from db import db


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    db.init_app(app)
    from routes.advisor_ai import bp as advisor_ai_bp
    from routes.constraints import bp as constraints_bp
    from routes.hot_flags import bp as hot_flags_bp
    from routes.people import bp as people_bp
    from routes.projects import bp as projects_bp
    from routes.proposals import bp as proposals_bp
    from routes.summary import bp as summary_bp
    from routes.triage import bp as triage_bp
    from routes.views import bp as views_bp

    for bp in (projects_bp, summary_bp, triage_bp, constraints_bp, hot_flags_bp, views_bp, proposals_bp,
               advisor_ai_bp, people_bp):
        app.register_blueprint(bp)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def demo_client(app, monkeypatch):
    """The full demo dataset behind a fake Depot, so tests never need a live Conway's Depot."""
    from demo_data import AVIONICS_ID, BRACKET_ID, NACELLE_ID, RADAR_ID, apply_demo_data

    projects = [
        {"id": RADAR_ID, "name": "Radar Housing Production", "has_manufacturing": True},
        {"id": BRACKET_ID, "name": "Bracket Assembly Program", "has_manufacturing": None},
        {"id": AVIONICS_ID, "name": "Avionics Bay Closeout", "has_manufacturing": True},
        {"id": NACELLE_ID, "name": "Nacelle Fairing Retrofit", "has_manufacturing": None},
        {"id": "no-mfg", "name": "Pure services project", "has_manufacturing": False},
    ]
    monkeypatch.setattr(depot_client, "fetch_projects", lambda: projects)
    monkeypatch.setattr(depot_client, "fetch_project",
                        lambda pid: next((p for p in projects if p["id"] == pid), None))
    journal = []
    monkeypatch.setattr(depot_client, "post_project_note",
                        lambda pid, person_id, body: journal.append((pid, person_id, body)) or True)
    app.journal = journal
    apply_demo_data()
    return app.test_client()
