"""
Mocked S4 manufacturing data for the demo projects beyond Bracket Assembly (see conways-depot's
demo_data.py for the fixed project ids). Radar Housing is the healthy, high-priority build with a
slipped forging; Nacelle is the low-priority project whose due date is close — MARTI's Impact rule
flags it, which is the whole point of the app. Idempotent (a material is added only if that
project doesn't already have its material number), so it can also be re-run on a live database
(backend/refresh_demo.py).
"""

from datetime import date, timedelta

from db import db
from models import AcquisitionOrder, Material, Routing, Tradeoff

RADAR_ID = "2a9c5e71-84d3-4f0b-b6a2-c13e7d9f5a08"
NACELLE_ID = "35fe3413-20e9-4762-8828-029ecade70c2"


def _today(days: int) -> date:
    return date.today() + timedelta(days=days)


# project -> [(material number, description, procurement type, [routing ops], [orders])]
# routing op: (seq, name, work center, status); order: (po number, status, need in days, promise in days)
MATERIALS = {
    RADAR_ID: [
        ("5310-7001", "Radar Housing, Machined", "E", [
            (10, "Saw & Rough", "SAW-1", "complete"),
            (20, "5-Axis Machining", "MACH-5", "in_process"),
            (30, "Deburr & Clean", "FIN-1", "not_started"),
            (40, "CMM Inspection", "QA-2", "not_started"),
            (50, "Anodize", "SURF-1", "not_started"),
        ], []),
        ("5310-7002", "Titanium Forging Blank", "F", [], [("PO-90412", "released", 6, 20)]),
        ("5310-7010", "Connector Kit", "F", [], [("PO-90455", "open", 30, 28)]),
    ],
    NACELLE_ID: [
        ("6201-3301", "Nacelle Fairing, Composite", "X", [
            (10, "Lay-up", "COMP-1", "in_process"),
            (20, "Autoclave Cure", "AUTO-1", "not_started"),
            (30, "Trim & Drill", "MACH-2", "not_started"),
            (40, "NDI Inspection", "QA-1", "not_started"),
        ], []),
        ("6201-3350", "Honeycomb Core Stock", "F", [], [("PO-77120", "released", 5, 11)]),
    ],
}

# project -> (priority, due in days)
TRADEOFFS = {
    RADAR_ID: ("high", 45),
    NACELLE_ID: ("low", 9),  # low priority + due within 14 days -> Impact flags it
}


def apply_demo_materials() -> int:
    added = 0
    for project_id, materials in MATERIALS.items():
        for number, description, procurement, ops, orders in materials:
            if Material.query.filter_by(depot_project_id=project_id, material_number=number).first():
                continue
            m = Material(
                depot_project_id=project_id, material_number=number,
                description=description, procurement_type=procurement,
            )
            db.session.add(m)
            db.session.flush()
            for seq, name, work_center, status in ops:
                db.session.add(Routing(material_id=m.id, operation_seq=seq, operation_name=name, work_center=work_center, status=status))
            for po, status, need, promise in orders:
                db.session.add(AcquisitionOrder(material_id=m.id, order_number=po, status=status, need_date=_today(need), promise_date=_today(promise)))
            added += 1
    for project_id, (priority, due) in TRADEOFFS.items():
        if Tradeoff.query.filter_by(depot_project_id=project_id).first() is None:
            db.session.add(Tradeoff(depot_project_id=project_id, priority=priority, due_date=_today(due)))
    db.session.commit()
    return added
