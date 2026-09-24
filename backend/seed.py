"""
Seed data for local development — MARTI's mocked S4 data and initial Triage ranking, against
real Conway's Depot demo projects rather than invented ones, the same "use real seeded demo
projects" rule every sibling app follows. See demo_data.py for the dataset and the story it's
built to tell."""

from models import WorkCenter


def seed_if_empty():
    if WorkCenter.query.first() is not None:
        return

    from demo_data import apply_demo_data

    apply_demo_data()
