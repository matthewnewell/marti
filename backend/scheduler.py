"""
Impact — MARTI's forecast. Computed fresh on every read, never stored.

**The model, in one paragraph**: projects are loaded onto shared work centers in Triage rank
order. Rank 1 books capacity first; every lower-ranked project gets whatever capacity is left.
Each remaining operation needs its S4 standard hours (setup + run × quantity; an operation already
under way needs only the run time for its unconfirmed quantity) at its work center's S4 available
hours per day. An operation can't start before the one ahead of it finishes, or before the material
allocated to it (RESB-VORNR) is available. The last operation's finish is the project's projected
finish, and the gap to its need-by date is the Impact.

**What it deliberately doesn't do**: no efficiency factors, no historical-actuals correction, no
invented lead times. The only numbers used are ones S4 holds. When S4 can't date something (a PR
with no PO, a missing master, an MRB hold awaiting disposition), the project is marked *blocked*
with that reason instead of getting a made-up date. Standard hours are known to be imperfect for
small-lot work, so the UI labels these as standard-hours forecasts. They're good for comparing
one ranking with another, not for promising a customer a date.

The calendar is Monday–Friday (a stand-in for the S4 factory calendar, no holidays).

**Levers** (Constraints' what-if sandbox) change the supply side: added hours, moved labor, new
equipment, outsourcing an operation for a turnaround the user types in, or expediting a
material to a date the user types in (those two typed values are the inputs that aren't S4,
labeled as such in the UI). They're never stored as fact. A lever
is a scenario until someone changes the real capacity in S4.

`Snapshot` loads everything from the database once. `forecast()` is a pure function of a
snapshot, a ranking, and today, so a what-if ranking costs one extra call, and tests don't need
a database at all.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

AT_RISK_SLACK_DAYS = 5  # MARTI's own display threshold, not an S4 fact


# --- calendar --------------------------------------------------------------------------------


def _first_workday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def day_to_date(start: date, day: int) -> date:
    d = start
    remaining = day
    while remaining > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            remaining -= 1
    return d


def date_to_day(start: date, d: date) -> int:
    """Workday index of `d` relative to `start` (0 for anything on or before start)."""
    if d <= start:
        return 0
    n = 0
    cur = start
    while cur < d:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


# --- snapshot --------------------------------------------------------------------------------


@dataclass
class Snapshot:
    work_centers: dict = field(default_factory=dict)  # code -> WorkCenter
    masters: dict = field(default_factory=dict)  # material_number -> MaterialMaster
    orders_by_project: dict = field(default_factory=lambda: defaultdict(list))
    pos: dict = field(default_factory=lambda: defaultdict(list))  # (project, material) -> [PO]
    prs: dict = field(default_factory=lambda: defaultdict(list))  # (project, material) -> [PR]
    open_holds: set = field(default_factory=set)  # (order_id, seq) with an open MRB hold
    notifications: dict = field(default_factory=lambda: defaultdict(list))  # order_id -> [QN]

    @classmethod
    def load(cls) -> "Snapshot":
        from models import (
            MaterialMaster, ProductionOrder, PurchaseOrder, PurchaseRequisition,
            QualityNotification, WorkCenter,
        )

        s = cls()
        s.work_centers = {w.code: w for w in WorkCenter.query.all()}
        s.masters = {m.material_number: m for m in MaterialMaster.query.all()}
        for o in ProductionOrder.query.order_by(ProductionOrder.order_number).all():
            s.orders_by_project[o.depot_project_id].append(o)
        for po in PurchaseOrder.query.order_by(PurchaseOrder.po_number).all():
            s.pos[(po.depot_project_id, po.material_number)].append(po)
        for pr in PurchaseRequisition.query.order_by(PurchaseRequisition.pr_number).all():
            s.prs[(pr.depot_project_id, pr.material_number)].append(pr)
        for qn in QualityNotification.query.order_by(QualityNotification.created_at).all():
            s.notifications[qn.order_id].append(qn)
            if qn.designator == "mrb_hold" and qn.closed_at is None:
                s.open_holds.add((qn.order_id, qn.operation_seq))
        return s

    def producing_order(self, project_id: str, material_number: str):
        for o in self.orders_by_project.get(project_id, []):
            if o.material_number == material_number:
                return o
        return None


# --- operation state (actuals only, no forecast) ---------------------------------------------


def operation_states(order, snap: Snapshot, now: datetime) -> list[dict]:
    """Where each operation stands from S4 confirmations alone: arrival (previous op's final
    confirmation, or order release), start, finish, and wall-clock dwell. `state` is one of
    done / in_process / queued / on_hold / not_arrived."""
    out = []
    prev_finish = order.released_at
    for op in order.operations:
        arrived_at = prev_finish
        if op.finished_at:
            state = "done"
        elif (order.id, op.seq) in snap.open_holds:
            state = "on_hold"
        elif op.started_at:
            state = "in_process"
        elif arrived_at:
            state = "queued"
        else:
            state = "not_arrived"

        end = op.finished_at or now
        dwell_hours = (end - arrived_at).total_seconds() / 3600 if arrived_at else None
        wait_hours = None  # queue time before work began
        if arrived_at and op.started_at:
            wait_hours = (op.started_at - arrived_at).total_seconds() / 3600
        elif arrived_at and state in ("queued", "on_hold"):
            wait_hours = (now - arrived_at).total_seconds() / 3600

        out.append({
            "op": op,
            "state": state,
            "arrived_at": arrived_at,
            "dwell_hours": dwell_hours,
            "wait_hours": wait_hours,
        })
        prev_finish = op.finished_at
    return out


def remaining_hours(op, order_qty: float, state: str) -> float:
    if state == "done":
        return 0.0
    if state == "in_process":
        return max(order_qty - op.yield_qty, 0) * op.run_hours_per_unit
    return op.setup_hours + order_qty * op.run_hours_per_unit


# --- supply ----------------------------------------------------------------------------------

STAGE_LABEL = {
    "no_master": "No material master",
    "no_pr": "No PR",
    "pr_created": "PR created",
    "pr_released": "PR released",
    "po_placed": "PO placed (unconfirmed)",
    "po_confirmed": "PO confirmed",
    "in_inspection": "Received, in inspection",
    "rejected": "Rejected at inspection",
    "in_stock": "In stock",
    "in_house": "Made in-house",
}


def supply_for(project_id: str, material_number: str, qty: float, snap: Snapshot, today: date) -> dict:
    """The furthest-along supply S4 knows about for one project's need of one material.
    `ready_date` is None when S4 can't date it. The forecast treats that as blocked."""
    master = snap.masters.get(material_number)
    base = {"stage": None, "ready_date": None, "confirmed": True, "ref": None, "past_due": False,
            "po": None, "pr": None}

    if master is None:
        return {**base, "stage": "no_master"}

    producing = snap.producing_order(project_id, material_number)
    if producing is not None:
        return {**base, "stage": "in_house", "ref": producing.order_number}

    pos = snap.pos.get((project_id, material_number), [])
    if pos:
        po = pos[-1]
        info = {**base, "po": po.to_dict(), "ref": po.po_number}
        if po.gr_date and po.inspection_status == "accepted":
            return {**info, "stage": "in_stock", "ready_date": today}
        if po.gr_date and po.inspection_status == "rejected":
            return {**info, "stage": "rejected"}
        if po.gr_date:
            # Physically here; the usage decision is the last step. Treat as usable today.
            return {**info, "stage": "in_inspection", "ready_date": today}
        promised = po.confirmed_date or po.requested_date
        stage = "po_confirmed" if po.confirmed_date else "po_placed"
        past_due = promised < today
        return {**info, "stage": stage, "ready_date": max(promised, today),
                "confirmed": po.confirmed_date is not None, "past_due": past_due}

    if master.unrestricted_stock >= qty:
        return {**base, "stage": "in_stock", "ref": "plant stock", "ready_date": today}

    prs = snap.prs.get((project_id, material_number), [])
    if prs:
        pr = prs[-1]
        stage = "pr_released" if pr.release_status == "released" else "pr_created"
        return {**base, "stage": stage, "pr": pr.to_dict(), "ref": pr.pr_number}

    return {**base, "stage": "no_pr"}


# --- forecast --------------------------------------------------------------------------------


_EPS = 1e-9


def _end_day(t: float) -> int:
    """Workday an end time falls on: 2.0 is the end of day 1, not the start of day 2."""
    return max(math.ceil(t - _EPS) - 1, 0)


_MAX_DAYS = 2000  # a work center with no capacity left forever would otherwise loop forever


def _book(load: dict, cap_at, earliest: float, hours: float) -> tuple[float, float]:
    """Consume `hours` of a work center's per-day capacity, starting no earlier than `earliest`.
    Time is in fractional workdays (1.5 = midway through day 1), so a step can't use the part of
    a day before the step ahead of it finished. Hours already booked on a day are treated as
    filling it from the start. `cap_at(day)` is that day's capacity in hours. Returns
    (start, finish)."""
    day, offset = int(earliest), earliest - int(earliest)
    start = None
    remaining = hours
    while day < _MAX_DAYS:
        capacity = cap_at(day)
        if capacity <= _EPS:
            day, offset = day + 1, 0.0
            continue
        begin = max(offset, load[day] / capacity)
        free = capacity * (1 - begin)
        if free > _EPS:
            take = min(free, remaining)
            if start is None:
                start = day + begin
            load[day] += take
            remaining -= take
            if remaining <= _EPS:
                return start, day + begin + take / capacity
        day, offset = day + 1, 0.0
    return (start if start is not None else float(day)), float(day)


LEVER_TYPES = ("add_hours", "move_labor", "add_equipment", "outsource", "expedite_material")


def _capacity_fn(snap: Snapshot, levers: list[dict], start: date):
    """cap_at(work_center, day) with every capacity lever applied on top of the S4 capacity.
    add_hours / add_equipment add hours per day to one work center from start_date (through
    end_date, if given); move_labor takes them from one work center and gives them to another."""
    deltas = defaultdict(list)  # wc -> [(from_day, to_day or None, hours)]

    def span(lv):
        s_day = date_to_day(start, date.fromisoformat(lv["start_date"])) if lv.get("start_date") else 0
        e_day = date_to_day(start, date.fromisoformat(lv["end_date"])) if lv.get("end_date") else None
        return s_day, e_day

    for lv in levers:
        hours = float(lv.get("hours_per_day") or 0)
        if lv["type"] in ("add_hours", "add_equipment"):
            deltas[lv["work_center"]].append((*span(lv), hours))
        elif lv["type"] == "move_labor":
            deltas[lv["from_work_center"]].append((*span(lv), -hours))
            deltas[lv["to_work_center"]].append((*span(lv), hours))

    def cap_at(wc: str, day: int) -> float:
        base = snap.work_centers[wc].capacity_hours_per_day
        extra = sum(h for s_day, e_day, h in deltas.get(wc, ()) if day >= s_day and (e_day is None or day <= e_day))
        return max(base + extra, 0.0)

    return cap_at


def _ordered_for_build(orders: list, project_id: str | None = None) -> list:
    """Sub-assembly orders before the orders that consume their output."""
    made_here = {o.material_number: o for o in orders}
    done, out = set(), []

    def visit(o):
        if o.id in done:
            return
        done.add(o.id)
        for c in o.components:
            dep = made_here.get(c.material_number)
            if dep is not None and dep.id != o.id:
                visit(dep)
        out.append(o)

    for o in orders:
        visit(o)
    return out


def forecast(snap: Snapshot, ranking: list[str], need_by: dict, today: date, now: datetime | None = None,
             levers: list[dict] | None = None) -> dict:
    now = now or datetime.combine(today, datetime.min.time())
    start = _first_workday(today)
    loads = defaultdict(lambda: defaultdict(float))  # work center -> day -> hours booked
    levers = levers or []
    cap_at = _capacity_fn(snap, levers, start)
    outsourced = {(lv["order_number"], int(lv["seq"])): float(lv["turnaround_days"])
                  for lv in levers if lv["type"] == "outsource"}
    # (project id or None for every project, material) -> the date the user says it could land
    expedited = {(lv.get("project_id"), lv["material_number"]): date.fromisoformat(lv["ready_date"])
                 for lv in levers if lv["type"] == "expedite_material"}

    projects, operations, components = {}, {}, {}
    order_finish: dict[str, float | None] = {}  # order id -> finish time in workdays (None = blocked)
    order_blocker: dict[str, dict] = {}

    for rank, project_id in enumerate(ranking, start=1):
        drivers = defaultdict(float)  # ("capacity", wc) / ("material", mn) -> days of waiting
        project_blocker = None
        finishes = []
        orders = _ordered_for_build(snap.orders_by_project.get(project_id, []), project_id)
        actual_finishes = []

        for order in orders:
            states = operation_states(order, snap, now)
            prev_finish_day = 0.0
            blocked = None
            for st in states:
                op = st["op"]
                if st["state"] == "done":
                    actual_finishes.append(op.finished_at.date())
                    operations[op.id] = {"state": "done"}
                    continue
                if blocked:
                    operations[op.id] = {"state": st["state"], "blocked": blocked}
                    continue
                if st["state"] == "on_hold":
                    blocked = {"kind": "hold", "order": order.order_number, "seq": op.seq,
                               "reason": f"MRB hold on {order.order_number} op {op.seq} awaiting disposition"}
                    operations[op.id] = {"state": "on_hold", "blocked": blocked}
                    continue

                mat_day, mat_driver = 0.0, None
                op_components = [c for c in order.components if c.operation_seq == op.seq]
                for c in op_components:
                    sup = supply_for(project_id, c.material_number, c.quantity, snap, today)
                    ready_day = None
                    exp = expedited.get((project_id, c.material_number)) or expedited.get((None, c.material_number))
                    if exp is not None and sup["stage"] not in ("in_house", "in_stock", "in_inspection"):
                        ready_day = date_to_day(start, max(exp, today))
                    elif sup["stage"] == "in_house":
                        dep = snap.producing_order(project_id, c.material_number)
                        ready_day = order_finish.get(dep.id)
                        if ready_day is None:
                            blocked = order_blocker.get(dep.id) or {
                                "kind": "material", "material": c.material_number,
                                "reason": f"{c.material_number} (made in-house) can't be forecast"}
                    elif sup["ready_date"] is not None:
                        ready_day = date_to_day(start, sup["ready_date"])
                    elif not blocked:
                        blocked = {"kind": "material", "material": c.material_number,
                                   "stage": sup["stage"],
                                   "reason": f"{c.material_number}: {STAGE_LABEL[sup['stage']].lower()}, no date from S4"}
                    # Every component on the step gets a need date, even after one blocks it.
                    components[c.id] = {"supply": sup, "ready_day": ready_day,
                                        "need_day": prev_finish_day}
                    if ready_day is not None and st["state"] != "in_process" and ready_day > mat_day:
                        mat_day, mat_driver = ready_day, c.material_number
                if blocked:
                    operations[op.id] = {"state": st["state"], "blocked": blocked}
                    continue

                earliest = max(prev_finish_day, mat_day)
                if mat_driver and mat_day > prev_finish_day:
                    drivers[("material", mat_driver)] += mat_day - prev_finish_day
                hours = remaining_hours(op, order.quantity, st["state"])
                vendor_days = outsourced.get((order.order_number, op.seq))
                if vendor_days is not None and st["state"] != "in_process":
                    # Off the work center entirely: the vendor's turnaround, no shop capacity.
                    s_day, f_day = earliest, earliest + vendor_days
                else:
                    vendor_days = None
                    s_day, f_day = _book(loads[op.work_center], lambda d, wc=op.work_center: cap_at(wc, d),
                                         earliest, hours)
                if s_day > earliest:
                    drivers[("capacity", op.work_center)] += s_day - earliest
                operations[op.id] = {
                    "state": st["state"], "hours": round(hours, 1),
                    "start_day": s_day, "finish_day": f_day, "earliest_day": earliest,
                    "capacity_wait_days": round(s_day - earliest, 1),
                    "material_wait_days": round(max(mat_day - prev_finish_day, 0), 1),
                    # What set this step's earliest start when it was material, not the step ahead.
                    "material_driver": mat_driver if mat_day > prev_finish_day else None,
                    "outsourced_days": vendor_days,
                }
                prev_finish_day = f_day

            order_finish[order.id] = None if blocked else prev_finish_day
            if blocked:
                order_blocker[order.id] = blocked
                project_blocker = project_blocker or blocked
            else:
                finishes.append(prev_finish_day)

        nb = need_by.get(project_id)
        work_left = any(op.finished_at is None for o in orders for op in o.operations)
        if not orders or project_blocker:
            finish_date = None
        elif work_left:
            finish_date = day_to_date(start, _end_day(max(finishes)))
        else:
            finish_date = max(actual_finishes) if actual_finishes else None

        slack = (nb - finish_date).days if (nb and finish_date) else None
        if not orders:
            status = "no_orders"
        elif project_blocker:
            status = "blocked"
        elif nb is None:
            status = "no_need_by"
        elif slack < 0:
            status = "late"
        elif slack < AT_RISK_SLACK_DAYS:
            status = "at_risk"
        else:
            status = "on_track"

        top = sorted(drivers.items(), key=lambda kv: -kv[1])[:3]
        projects[project_id] = {
            "rank": rank,
            "need_by": nb.isoformat() if nb else None,
            "projected_finish": finish_date.isoformat() if finish_date else None,
            "slack_days": slack,
            "status": status,
            "blocker": project_blocker,
            "drivers": [{"kind": k[0], "key": k[1], "days": round(v, 1)} for k, v in top if v >= 0.05],
        }

    # Dates for everything scheduled, now that every day index is final.
    # Times are fractional workdays: a start or availability falls on int(t), an end on _end_day(t).
    for info in operations.values():
        if "start_day" in info:
            info["start_date"] = day_to_date(start, int(info["start_day"])).isoformat()
            info["earliest_date"] = day_to_date(start, int(info["earliest_day"])).isoformat()
            info["finish_date"] = day_to_date(start, _end_day(info["finish_day"])).isoformat()
            for key in ("start_day", "finish_day", "earliest_day"):
                info[key] = round(info[key], 2)
    for info in components.values():
        rd, nd = info["ready_day"], info["need_day"]
        info["need_date"] = day_to_date(start, int(nd)).isoformat()
        info["ready_date"] = day_to_date(start, int(rd)).isoformat() if rd is not None else None
        # Working days the material arrives after the step could otherwise start; 0 if on time.
        info["late_days"] = max(math.ceil(rd - nd - _EPS), 0) if rd is not None else None

    horizon = 20
    load_out, cap_out = {}, {}
    for code in snap.work_centers:
        booked = loads.get(code, {})
        load_out[code] = [round(booked.get(d, 0.0), 1) for d in range(horizon)]
        cap_out[code] = [round(cap_at(code, d), 1) for d in range(horizon)]

    return {
        "as_of": today.isoformat(),
        "calendar_start": start.isoformat(),
        "projects": projects,
        "operations": operations,
        "components": components,
        "work_center_load": load_out,
        "work_center_capacity": cap_out,
        "order_finish_day": {k: (round(v, 2) if v is not None else None) for k, v in order_finish.items()},
    }
