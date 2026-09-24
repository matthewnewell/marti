"""The Impact forecast on small hand-built data: rank-ordered capacity loading, material gating,
and blocked-not-guessed behavior. Monday 2026-09-21 is day 0 throughout."""

from datetime import date, datetime, timedelta

import scheduler
from db import db
from models import (
    Component, MaterialMaster, Operation, ProductionOrder, PurchaseOrder, PurchaseRequisition,
    QualityNotification, WorkCenter,
)

MON = date(2026, 9, 21)
NOW = datetime(2026, 9, 21, 8, 0)


def _order(project, number, material, qty, ops, released=True):
    o = ProductionOrder(order_number=number, depot_project_id=project, material_number=material,
                        quantity=qty, released_at=NOW - timedelta(hours=10) if released else None)
    db.session.add(o)
    db.session.flush()
    for seq, wc, setup, run in ops:
        db.session.add(Operation(order_id=o.id, seq=seq, description=f"op {seq}", work_center=wc,
                                 setup_hours=setup, run_hours_per_unit=run))
    db.session.flush()
    return o


def _base(app):
    db.session.add(WorkCenter(code="MILL", description="Mill", capacity_hours_per_day=8))
    db.session.add(WorkCenter(code="QA", description="QA", capacity_hours_per_day=8))
    db.session.add(MaterialMaster(material_number="OUT-A", description="A", procurement_type="E"))
    db.session.add(MaterialMaster(material_number="OUT-B", description="B", procurement_type="E"))


def _run(ranking, need_by=None):
    db.session.commit()
    snap = scheduler.Snapshot.load()
    return scheduler.forecast(snap, ranking, need_by or {}, MON, NOW)


def test_calendar_skips_weekends():
    assert scheduler.day_to_date(MON, 5) == date(2026, 9, 28)
    assert scheduler.date_to_day(MON, date(2026, 9, 28)) == 5
    assert scheduler.date_to_day(MON, date(2026, 9, 1)) == 0


def test_higher_rank_books_shared_capacity_first(app):
    _base(app)
    _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 16)])  # two full days
    _order("B", "B1", "OUT-B", 1, [(10, "MILL", 0, 16)])

    ab = _run(["A", "B"])
    assert ab["projects"]["A"]["projected_finish"] == "2026-09-22"
    assert ab["projects"]["B"]["projected_finish"] == "2026-09-24"
    assert ab["projects"]["B"]["drivers"][0] == {"kind": "capacity", "key": "MILL", "days": 2.0}

    ba = _run(["B", "A"])
    assert ba["projects"]["A"]["projected_finish"] == "2026-09-24"
    assert ba["projects"]["B"]["projected_finish"] == "2026-09-22"


def test_slack_and_status_from_need_by(app):
    _base(app)
    _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 8)])
    f = _run(["A"], {"A": date(2026, 9, 20)})
    assert f["projects"]["A"]["slack_days"] == -1
    assert f["projects"]["A"]["status"] == "late"
    f = _run(["A"], {"A": date(2026, 10, 30)})
    assert f["projects"]["A"]["status"] == "on_track"


def test_operation_waits_for_confirmed_po(app):
    _base(app)
    db.session.add(MaterialMaster(material_number="RAW", description="raw"))
    o = _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 4)])
    db.session.add(Component(order_id=o.id, operation_seq=10, material_number="RAW", quantity=1))
    db.session.add(PurchaseOrder(po_number="PO1", depot_project_id="A", material_number="RAW", quantity=1,
                                 created_on=MON, requested_date=date(2026, 9, 23),
                                 confirmed_date=date(2026, 9, 25)))
    f = _run(["A"])
    assert f["projects"]["A"]["projected_finish"] == "2026-09-25"  # confirmed date, not requested
    assert f["projects"]["A"]["drivers"][0]["kind"] == "material"


def test_pr_without_po_blocks_instead_of_guessing(app):
    _base(app)
    db.session.add(MaterialMaster(material_number="RAW", description="raw"))
    o = _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 4), (20, "QA", 0, 1)])
    db.session.add(Component(order_id=o.id, operation_seq=20, material_number="RAW", quantity=1))
    db.session.add(PurchaseRequisition(pr_number="PR1", depot_project_id="A", material_number="RAW",
                                       quantity=1, created_on=MON))
    f = _run(["A"])
    p = f["projects"]["A"]
    assert p["status"] == "blocked"
    assert p["projected_finish"] is None
    assert "RAW" in p["blocker"]["reason"]


def test_missing_master_blocks(app):
    _base(app)
    o = _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 4)])
    db.session.add(Component(order_id=o.id, operation_seq=10, material_number="NOPE", quantity=1))
    f = _run(["A"])
    assert f["projects"]["A"]["status"] == "blocked"


def test_open_mrb_hold_blocks(app):
    _base(app)
    o = _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 4)])
    db.session.add(QualityNotification(notification_number="Q1", order_id=o.id, operation_seq=10,
                                       designator="mrb_hold", description="held", created_at=NOW))
    f = _run(["A"])
    assert f["projects"]["A"]["blocker"]["kind"] == "hold"


def test_subassembly_finishes_before_parent_starts(app):
    _base(app)
    top = _order("A", "A-TOP", "OUT-A", 1, [(10, "QA", 0, 8)], released=False)
    db.session.add(Component(order_id=top.id, operation_seq=10, material_number="OUT-B", quantity=1))
    _order("A", "A-SUB", "OUT-B", 1, [(10, "MILL", 0, 16)])
    f = _run(["A"])
    assert f["projects"]["A"]["projected_finish"] == "2026-09-23"


def test_in_process_needs_only_unconfirmed_run_time(app):
    _base(app)
    o = _order("A", "A1", "OUT-A", 4, [(10, "MILL", 8, 2)])
    op = o.operations[0]
    op.started_at = NOW - timedelta(hours=5)
    op.yield_qty = 3
    states = scheduler.operation_states(o, scheduler.Snapshot.load(), NOW)
    assert states[0]["state"] == "in_process"
    assert scheduler.remaining_hours(op, 4, "in_process") == 2


def test_dwell_counts_from_previous_operation_finish(app):
    _base(app)
    o = _order("A", "A1", "OUT-A", 1, [(10, "MILL", 0, 1), (20, "QA", 0, 1)])
    o.operations[0].started_at = NOW - timedelta(hours=30)
    o.operations[0].finished_at = NOW - timedelta(hours=24)
    db.session.commit()
    states = scheduler.operation_states(o, scheduler.Snapshot.load(), NOW)
    assert states[1]["state"] == "queued"
    assert round(states[1]["dwell_hours"]) == 24
