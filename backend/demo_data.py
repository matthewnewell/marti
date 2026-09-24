"""
Mocked S4 data for MARTI's demo, against the four real Conway's Depot demo projects that have a
manufacturing side (fixed ids from conways-depot's seed/demo data). Timestamps are relative to
now so dwell times and promise dates stay meaningful whenever the database is seeded.

The story it's built to tell:
- All four projects share the 5-axis mill (MACH-5). That's the constraint. Nacelle's big trim &
  drill job has been queued there for days.
- Ranked as seeded, Nacelle (last) misses its need-by date. Move it up and Bracket or Radar pays
  for it. That's the tradeoff leadership is actually making.
- Avionics Bay can't be forecast at all: its final assembly waits on a fastener kit whose PR
  nobody has released and a bonding strap with no S4 master. Its cable brackets are also on an
  MRB hold.
- Bracket has open weld rework and a hardware kit PO the supplier hasn't confirmed.
- A completed prior Bracket lot (BO-2990) gives the work centers some dwell history.
- Radar's top assembly is three levels deep: the housing assembly (RO-1000) takes the machined
  housing (RO-1001) and a cover assembly (RO-1002), and the cover assembly takes a machined cover
  plate (RO-1003) and hinge bracket (RO-1004).
"""

from datetime import date, datetime, timedelta

from db import db
from models import (
    Component, MaterialMaster, Operation, PriorityChange, ProductionOrder, ProjectRank,
    PurchaseOrder, PurchaseRequisition, QualityNotification, WorkCenter, _now,
)

RADAR_ID = "2a9c5e71-84d3-4f0b-b6a2-c13e7d9f5a08"
BRACKET_ID = "ff5bfe0b-7b18-4337-a464-6517c6f6c13b"
AVIONICS_ID = "6f1b8d23-0a4e-47c5-8e93-5b7c2a1d9e64"
NACELLE_ID = "35fe3413-20e9-4762-8828-029ecade70c2"

WORK_CENTERS = [
    ("KIT-1", "Kitting", 8),
    ("SAW-1", "Saw", 8),
    ("WELD-2", "Weld cell", 8),
    ("MACH-2", "3-axis mill", 8),
    ("MACH-5", "5-axis mill", 16),
    ("COMP-1", "Composite lay-up", 8),
    ("AUTO-1", "Autoclave", 16),
    ("FIN-1", "Deburr & finish", 8),
    ("SURF-1", "Anodize / paint", 8),
    ("QA-1", "Inspection", 8),
    ("QA-2", "CMM", 8),
    ("ASSY-1", "Assembly", 8),
]

# material number, description, procurement type, unrestricted plant stock
MATERIALS = [
    ("5310-7000", "Radar Housing Assembly", "E", 0),
    ("5310-7001", "Radar Housing, Machined", "E", 0),
    ("5310-7002", "Titanium Forging Blank", "F", 0),
    ("5310-7010", "Connector Kit", "F", 0),
    ("5310-7015", "EMI Gasket", "F", 40),
    ("5310-7005", "Cover Assembly", "E", 0),
    ("5310-7006", "Cover Plate, Machined", "E", 0),
    ("5310-7007", "Captive Fastener", "F", 100),
    ("5310-7008", "Hinge Bracket, Machined", "E", 0),
    ("5310-7009", "Aluminum Bar, 7075", "F", 50),
    ("4302-1101", "Bracket Weldment (prior rev)", "E", 0),
    ("4302-1102", "Bracket Weldment", "E", 0),
    ("4302-2201", "Standard Hardware Kit", "F", 0),
    ("4302-0900", "Steel Plate, 0.25 in", "F", 60),
    ("7710-0400", "Avionics Tray", "E", 0),
    ("7710-0410", "Aluminum Plate, 6061", "F", 30),
    ("7710-0450", "Fastener Kit, Avionics Tray", "F", 0),
    ("7710-0500", "Cable Bracket", "E", 0),
    # 7710-0460 Bonding Strap deliberately has no master: it's on the eBOM only.
    ("6201-3301", "Nacelle Fairing, Composite", "X", 0),
    ("6201-3350", "Honeycomb Core Stock", "F", 0),
    ("6201-3390", "Insert Kit, Nacelle", "F", 0),
]


def _ago(hours: float) -> datetime:
    return _now().replace(microsecond=0) - timedelta(hours=hours)


def _in(days: int) -> date:
    return date.today() + timedelta(days=days)


# order number, project, material made, qty, released (hours ago or None), ops, components
# op: (seq, description, work center, setup h, run h/unit, started h ago, finished h ago, yield, scrap, rework)
# component: (op seq, material, qty, eBOM description if no master)
ORDERS = [
    ("RO-1001", RADAR_ID, "5310-7001", 4, 120, [
        (10, "Saw & rough", "SAW-1", 1, 1, 118, 110, 4, 0, 0),
        (20, "5-axis machining", "MACH-5", 4, 8, 60, None, 1, 0, 0),
        (30, "Deburr & clean", "FIN-1", 1, 1.5, None, None, 0, 0, 0),
        (40, "CMM inspection", "QA-2", 1, 2, None, None, 0, 0, 0),
        (50, "Anodize", "SURF-1", 2, 1, None, None, 0, 0, 0),
    ], [(10, "5310-7002", 4, None)]),
    ("RO-1000", RADAR_ID, "5310-7000", 4, None, [
        (10, "Kit components", "KIT-1", 0.5, 0.5, None, None, 0, 0, 0),
        (20, "Assemble housing", "ASSY-1", 2, 4, None, None, 0, 0, 0),
        (30, "Final inspection", "QA-1", 1, 1.5, None, None, 0, 0, 0),
    ], [(20, "5310-7001", 4, None), (20, "5310-7005", 4, None), (20, "5310-7010", 4, None), (20, "5310-7015", 8, None)]),
    ("RO-1002", RADAR_ID, "5310-7005", 4, None, [
        (10, "Install fasteners", "ASSY-1", 0.5, 0.5, None, None, 0, 0, 0),
        (20, "Inspect", "QA-1", 0.5, 0.25, None, None, 0, 0, 0),
    ], [(10, "5310-7006", 4, None), (10, "5310-7008", 4, None), (10, "5310-7007", 16, None)]),
    ("RO-1003", RADAR_ID, "5310-7006", 4, 30, [
        (10, "Saw", "SAW-1", 0.5, 0.25, 28, 26, 4, 0, 0),
        (20, "Mill", "MACH-2", 1.5, 1.5, 6, None, 1, 0, 0),
        (30, "Deburr", "FIN-1", 0.5, 0.5, None, None, 0, 0, 0),
    ], [(10, "5310-7009", 4, None)]),
    ("RO-1004", RADAR_ID, "5310-7008", 4, 20, [
        (10, "5-axis mill", "MACH-5", 2, 2, None, None, 0, 0, 0),
        (20, "CMM inspection", "QA-2", 0.5, 0.5, None, None, 0, 0, 0),
    ], [(10, "5310-7009", 4, None)]),

    ("BO-2990", BRACKET_ID, "4302-1101", 10, 700, [
        (10, "Kitting", "KIT-1", 0.5, 0.1, 690, 686, 10, 0, 0),
        (20, "Weld", "WELD-2", 1, 2, 640, 600, 10, 0, 0),
        (30, "Machine", "MACH-5", 2, 2.5, 470, 440, 10, 0, 0),
        (40, "Final inspection", "QA-1", 1, 0.5, 400, 395, 10, 0, 0),
    ], [(10, "4302-0900", 10, None)]),
    ("BO-3001", BRACKET_ID, "4302-1102", 10, 150, [
        (10, "Kitting", "KIT-1", 0.5, 0.1, 146, 144, 10, 0, 0),
        (20, "Weld", "WELD-2", 1, 2, 90, None, 6, 0, 2),
        (30, "Machine", "MACH-5", 2, 2.5, None, None, 0, 0, 0),
        (40, "Final inspection", "QA-1", 1, 0.5, None, None, 0, 0, 0),
    ], [(10, "4302-0900", 10, None), (40, "4302-2201", 10, None)]),

    ("AO-4001", AVIONICS_ID, "7710-0400", 8, 72, [
        (10, "Saw", "SAW-1", 0.5, 0.25, 70, 66, 8, 0, 0),
        (20, "Rough mill", "MACH-2", 2, 1.5, 60, 30, 8, 0, 0),
        (30, "Finish mill", "MACH-5", 3, 2, None, None, 0, 0, 0),
        (40, "Deburr", "FIN-1", 0.5, 0.5, None, None, 0, 0, 0),
        (50, "Chem film", "SURF-1", 1, 0.5, None, None, 0, 0, 0),
        (60, "Install hardware", "ASSY-1", 1, 1, None, None, 0, 0, 0),
        (70, "Final inspection", "QA-1", 1, 0.5, None, None, 0, 0, 0),
    ], [(10, "7710-0410", 8, None), (60, "7710-0450", 8, None), (60, "7710-0460", 16, "Bonding Strap, Tinned Cu")]),
    ("AO-4002", AVIONICS_ID, "7710-0500", 20, 96, [
        (10, "Machine", "MACH-2", 1, 0.4, 90, 70, 20, 0, 0),
        (20, "Inspect", "QA-1", 0.5, 0.2, 60, None, 0, 0, 0),
        (30, "Chem film", "SURF-1", 1, 0.1, None, None, 0, 0, 0),
    ], [(10, "7710-0410", 4, None)]),

    ("NO-2001", NACELLE_ID, "6201-3301", 2, 220, [
        (10, "Lay-up", "COMP-1", 2, 10, 210, 170, 2, 0, 1),
        (20, "Autoclave cure", "AUTO-1", 1, 6, 150, 120, 2, 0, 0),
        (30, "Trim & drill", "MACH-5", 4, 22, None, None, 0, 0, 0),
        (40, "NDI inspection", "QA-1", 1, 6, None, None, 0, 0, 0),
        (50, "Paint", "SURF-1", 2, 3, None, None, 0, 0, 0),
    ], [(10, "6201-3350", 2, None), (30, "6201-3390", 2, None)]),
]

# po, pr, project, material, supplier, qty, created (days ago), requested (days from now),
# confirmed (days from now or None), gr (days ago or None), inspection status
PURCHASE_ORDERS = [
    ("4500012201", "10004411", RADAR_ID, "5310-7002", "Precision Forge Co.", 4, 40, -12, -12, 12, "accepted"),
    ("4500012288", "10004460", RADAR_ID, "5310-7010", "Amphenol Distribution", 4, 18, 8, 12, None, "none"),
    ("4500012310", "10004502", BRACKET_ID, "4302-2201", "Fastenal", 10, 6, 3, None, None, "none"),
    ("4500011950", "10004380", NACELLE_ID, "6201-3350", "Hexcel", 2, 50, -20, -18, 19, "accepted"),
    ("4500012255", "10004450", NACELLE_ID, "6201-3390", "Click Bond", 2, 25, -4, -2, None, "none"),
]

# pr, project, material, qty, release status, created (days ago)
PURCHASE_REQUISITIONS = [
    ("10004530", AVIONICS_ID, "7710-0450", 8, "not_released", 9),
]

# qmnum, order, op seq, designator, description, qty, created (h ago), closed (h ago or None)
QUALITY_NOTIFICATIONS = [
    ("200008811", "NO-2001", 10, "rework", "Ply wrinkle on unit 2 — debulk and re-lay", 1, 185, 172),
    ("200008890", "BO-3001", 20, "rework", "Porosity on 2 welds — grind and re-weld", 2, 40, None),
    ("200008902", "AO-4002", 20, "mrb_hold", "Hole position out of tolerance on 20 pcs — MRB disposition pending", 20, 52, None),
    ("200008850", "BO-2990", 30, "defect", "Burr on edge, removed at inspection", 1, 445, 430),
]

# rank order and need-by (days from now)
RANKING = [
    (RADAR_ID, 30),
    (BRACKET_ID, 7),
    (AVIONICS_ID, 35),
    (NACELLE_ID, 11),
]


def apply_demo_data():
    """Load the whole demo set. Only runs against an empty database (see seed.py)."""
    for code, desc, cap in WORK_CENTERS:
        db.session.add(WorkCenter(code=code, description=desc, capacity_hours_per_day=cap))
    for number, desc, proc, stock in MATERIALS:
        db.session.add(MaterialMaster(material_number=number, description=desc,
                                      procurement_type=proc, unrestricted_stock=stock))
    db.session.flush()

    orders = {}
    for number, project, material, qty, released, ops, comps in ORDERS:
        o = ProductionOrder(order_number=number, depot_project_id=project, material_number=material,
                            quantity=qty, released_at=_ago(released) if released is not None else None)
        db.session.add(o)
        db.session.flush()
        orders[number] = o
        for seq, desc, wc, setup, run, started, finished, yld, scrap, rework in ops:
            db.session.add(Operation(
                order_id=o.id, seq=seq, description=desc, work_center=wc,
                setup_hours=setup, run_hours_per_unit=run,
                started_at=_ago(started) if started is not None else None,
                finished_at=_ago(finished) if finished is not None else None,
                yield_qty=yld, scrap_qty=scrap, rework_qty=rework,
            ))
        for seq, material_number, cqty, ebom_desc in comps:
            db.session.add(Component(order_id=o.id, operation_seq=seq, material_number=material_number,
                                     quantity=cqty, description=ebom_desc))

    for po, pr, project, material, supplier, qty, created, req, conf, gr, insp in PURCHASE_ORDERS:
        db.session.add(PurchaseOrder(
            po_number=po, pr_number=pr, depot_project_id=project, material_number=material,
            supplier=supplier, quantity=qty, created_on=_in(-created), requested_date=_in(req),
            confirmed_date=_in(conf) if conf is not None else None,
            gr_date=_in(-gr) if gr is not None else None, inspection_status=insp,
        ))
    for pr, project, material, qty, status, created in PURCHASE_REQUISITIONS:
        db.session.add(PurchaseRequisition(pr_number=pr, depot_project_id=project, material_number=material,
                                           quantity=qty, release_status=status, created_on=_in(-created)))

    for qmnum, order_number, seq, designator, desc, qty, created, closed in QUALITY_NOTIFICATIONS:
        db.session.add(QualityNotification(
            notification_number=qmnum, order_id=orders[order_number].id, operation_seq=seq,
            designator=designator, description=desc, quantity=qty, created_at=_ago(created),
            closed_at=_ago(closed) if closed is not None else None,
        ))

    ids = [pid for pid, _ in RANKING]
    for rank, (pid, need) in enumerate(RANKING, start=1):
        db.session.add(ProjectRank(depot_project_id=pid, rank=rank, need_by=_in(need)))
    db.session.add(PriorityChange(
        changed_by="Program Leadership", reason="Initial ranking for the quarter.",
        before=[], after=ids, changed_at=_ago(24 * 12),
    ))
    db.session.commit()
