"""Wipe MARTI's own database and reload the demo set, so dwell times and promise dates are
relative to today again. Destroys any Triage re-ranks, priority changes, proposals, and hot flags.

    cd backend && .venv/bin/python refresh_demo.py
"""

from app import create_app
from db import db
from demo_data import apply_demo_data

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        apply_demo_data()
        print("MARTI demo data reloaded.")
