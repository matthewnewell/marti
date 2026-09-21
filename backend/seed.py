"""
Seed data for local development — mocked S4 material/acquisition/routing rows plus a Tradeoff
entry, against a real Conway's Depot demo project (Bracket Assembly Program) rather than an
invented one, same "use real seeded demo projects" discipline every sibling app follows."""

from datetime import date, timedelta

from db import db
from models import AcquisitionOrder, Material, Routing, Tradeoff

# Bracket Assembly Program — the same project Value Stream's own demo map and WinMax's
# demo pursuit are already crosswalked to (see conways-depot's seed.py).
BRACKET_ASSEMBLY_PROJECT_ID = "ff5bfe0b-7b18-4337-a464-6517c6f6c13b"


def seed_if_empty():
    if Material.query.first() is not None:
        return

    weldment = Material(
        depot_project_id=BRACKET_ASSEMBLY_PROJECT_ID,
        material_number="4302-1102",
        description="Bracket Weldment",
        procurement_type="E",  # in-house production — the manufacturing trigger
    )
    hardware_kit = Material(
        depot_project_id=BRACKET_ASSEMBLY_PROJECT_ID,
        material_number="4302-2201",
        description="Standard Hardware Kit",
        procurement_type="F",  # purchased — doesn't trigger manufacturing on its own
    )
    db.session.add_all([weldment, hardware_kit])
    db.session.flush()  # assign ids before the child rows reference them

    db.session.add_all([
        Routing(material_id=weldment.id, operation_seq=10, operation_name="Kitting", work_center="KIT-1", status="complete"),
        Routing(material_id=weldment.id, operation_seq=20, operation_name="Weld", work_center="WELD-2", status="in_process"),
        Routing(material_id=weldment.id, operation_seq=30, operation_name="Machine", work_center="MACH-1", status="not_started"),
        Routing(material_id=weldment.id, operation_seq=40, operation_name="Final Inspection", work_center="QA-1", status="not_started"),
    ])
    db.session.add(
        AcquisitionOrder(
            material_id=hardware_kit.id,
            order_number="PO-88213",
            status="open",
            need_date=date.today() + timedelta(days=10),
            promise_date=date.today() + timedelta(days=12),
        )
    )
    db.session.add(
        Tradeoff(
            depot_project_id=BRACKET_ASSEMBLY_PROJECT_ID,
            priority="medium",
            # Within the 14-day Impact window on purpose, so the seeded demo shows a real
            # flagged Impact rather than an all-green "nothing to see" state.
            due_date=date.today() + timedelta(days=8),
        )
    )
    db.session.commit()

    from demo_data import apply_demo_materials

    apply_demo_materials()
