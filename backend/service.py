"""
The read side every route shares: which projects are manufacturing projects, the current
Triage ranking, and the per-project / per-work-center views built from S4 actuals plus the
Impact forecast. Routes stay thin. They call in here and jsonify.
"""

from datetime import date, datetime
from statistics import median

import advisor
import depot_client
import scheduler
from db import db
from models import HotFlag, PriorityChange, ProductionOrder, ProjectRank, _iso, _now

# --- which projects, in what order -----------------------------------------------------------


def manufacturing_projects(depot_projects: list[dict] | None) -> dict[str, str]:
    """{project id: name} for every project MARTI covers. A project qualifies if Conway's Depot
    flags has_manufacturing, or S4 has a production order against it (either is enough, since
    the Depot flag is provisional). Depot unreachable means ids only, names unknown."""
    with_orders = {r[0] for r in db.session.query(ProductionOrder.depot_project_id).distinct()}
    ranked = {r.depot_project_id for r in ProjectRank.query.all()}
    if depot_projects is None:
        return {pid: None for pid in with_orders | ranked}
    out = {}
    for p in depot_projects:
        if p.get("has_manufacturing") or p["id"] in with_orders or p["id"] in ranked:
            out[p["id"]] = p["name"]
    return out


def current_ranking(project_ids) -> tuple[list[str], dict]:
    """(ids in rank order, {id: need_by}). A manufacturing project nobody has ranked yet goes
    to the bottom, so a new project is visible but never silently jumps the queue."""
    rows = {r.depot_project_id: r for r in ProjectRank.query.all()}
    ranked = sorted((pid for pid in project_ids if pid in rows), key=lambda pid: rows[pid].rank)
    unranked = sorted(pid for pid in project_ids if pid not in rows)
    need_by = {pid: rows[pid].need_by for pid in rows}
    return ranked + unranked, need_by


def context(today: date | None = None, now: datetime | None = None):
    """Everything a view needs, loaded once: names, ranking, snapshot, forecast."""
    today = today or date.today()
    now = now or _now()
    depot = depot_client.fetch_projects()
    names = manufacturing_projects(depot)
    ranking, need_by = current_ranking(names.keys())
    snap = scheduler.Snapshot.load()
    fc = scheduler.forecast(snap, ranking, need_by, today, now)
    return {
        "today": today, "now": now, "depot_reachable": depot is not None, "names": names,
        "ranking": ranking, "need_by": need_by, "snap": snap, "forecast": fc,
        "bottleneck": _bottleneck(snap, now),
    }


def _bottleneck(snap, now) -> str | None:
    """The work center with the most days of unfinished work in front of it right now."""
    hours = {}
    for orders in snap.orders_by_project.values():
        for order in orders:
            for st in scheduler.operation_states(order, snap, now):
                if st["state"] in ("queued", "in_process", "on_hold"):
                    wc = st["op"].work_center
                    hours[wc] = hours.get(wc, 0) + scheduler.remaining_hours(st["op"], order.quantity, st["state"])
    if not hours:
        return None
    return max(hours, key=lambda wc: hours[wc] / max(snap.work_centers[wc].capacity_hours_per_day, 1e-6))


# --- per project -----------------------------------------------------------------------------


def _hours(h):
    return round(h, 1) if h is not None else None


def order_view(order, ctx) -> dict:
    snap, fc, now, today = ctx["snap"], ctx["forecast"], ctx["now"], ctx["today"]
    states = scheduler.operation_states(order, snap, now)
    qns = snap.notifications.get(order.id, [])
    ops = []
    current = None
    for st in states:
        op = st["op"]
        comps = []
        for c in order.components:
            if c.operation_seq != op.seq:
                continue
            sup = scheduler.supply_for(order.depot_project_id, c.material_number, c.quantity, snap, today)
            f = fc["components"].get(c.id, {})
            comps.append({
                "material_number": c.material_number,
                "description": (snap.masters[c.material_number].description
                                if c.material_number in snap.masters else c.description),
                "quantity": c.quantity,
                "stage": sup["stage"],
                "stage_label": scheduler.STAGE_LABEL[sup["stage"]],
                "ref": sup["ref"],
                "available_now": sup["ready_date"] is not None and sup["ready_date"] <= today
                                 and sup["stage"] in ("in_stock", "in_inspection"),
                "ready_date": f.get("ready_date") or _iso(sup["ready_date"]),
            })
        f = fc["operations"].get(op.id, {})
        view = {
            "id": op.id,
            "seq": op.seq,
            "description": op.description,
            "work_center": op.work_center,
            "state": st["state"],
            "setup_hours": op.setup_hours,
            "run_hours_per_unit": op.run_hours_per_unit,
            "standard_hours": _hours(op.setup_hours + order.quantity * op.run_hours_per_unit),
            "arrived_at": _iso(st["arrived_at"]),
            "started_at": _iso(op.started_at),
            "finished_at": _iso(op.finished_at),
            "dwell_hours": _hours(st["dwell_hours"]),
            "wait_hours": _hours(st["wait_hours"]),
            "yield_qty": op.yield_qty,
            "scrap_qty": op.scrap_qty,
            "rework_qty": op.rework_qty,
            "quality": [q.to_dict() for q in qns if q.operation_seq == op.seq],
            "components": comps,
            "forecast": {k: f.get(k) for k in ("start_date", "finish_date", "capacity_wait_days",
                                                "material_wait_days", "hours", "blocked")},
        }
        if current is None and st["state"] != "done":
            current = view
        ops.append(view)

    # Clear to build: the next step's material is physically here and nothing holds it.
    if current is None:
        ctb = {"status": "complete", "reason": "All operations confirmed."}
    elif current["state"] == "on_hold":
        ctb = {"status": "held", "reason": f"Op {current['seq']} is on MRB hold."}
    elif current["state"] == "in_process":
        ctb = {"status": "running", "reason": f"Op {current['seq']} is in process."}
    else:
        missing = [c for c in current["components"] if not c["available_now"]]
        if missing:
            ctb = {"status": "waiting_material",
                   "reason": "Waiting on " + ", ".join(f"{c['material_number']} ({c['stage_label'].lower()})" for c in missing),
                   "missing": [c["material_number"] for c in missing]}
        elif current["state"] == "not_arrived":
            ctb = {"status": "not_released", "reason": "Order not released yet."}
        else:
            ctb = {"status": "clear", "reason": f"Op {current['seq']} can start at {current['work_center']}."}

    master = snap.masters.get(order.material_number)
    finish_day = fc.get("order_finish_day", {}).get(order.id)
    finish_date = None
    if current is not None and finish_day is not None:
        start = date.fromisoformat(fc["calendar_start"])
        finish_date = scheduler.day_to_date(start, scheduler._end_day(finish_day)).isoformat()
    return {
        "order_id": order.id,
        "forecast_finish_date": finish_date,
        "forecast_blocked": current is not None and finish_day is None,
        "order_number": order.order_number,
        "material_number": order.material_number,
        "description": master.description if master else None,
        "quantity": order.quantity,
        "released_at": _iso(order.released_at),
        "current_seq": current["seq"] if current else None,
        "clear_to_build": ctb,
        "operations": ops,
    }


def acquisition_lines(project_id: str, ctx) -> list[dict]:
    """Every material the project's orders need, one line per component, with the furthest
    stage S4 knows (master → PR → PO → receipt → stock) and the forecast's need vs. ready date."""
    snap, fc, today = ctx["snap"], ctx["forecast"], ctx["today"]
    lines = []
    for order in snap.orders_by_project.get(project_id, []):
        for c in order.components:
            sup = scheduler.supply_for(project_id, c.material_number, c.quantity, snap, today)
            f = fc["components"].get(c.id, {})
            master = snap.masters.get(c.material_number)
            op_done = any(op.seq == c.operation_seq and op.finished_at for op in order.operations)
            lines.append({
                "material_number": c.material_number,
                "description": master.description if master else c.description,
                "master_exists": master is not None,
                "procurement_type": master.procurement_type if master else None,
                "quantity": c.quantity,
                "unit": master.unit if master else "EA",
                "order_number": order.order_number,
                "operation_seq": c.operation_seq,
                "consumed": op_done,
                "stage": sup["stage"],
                "stage_label": scheduler.STAGE_LABEL[sup["stage"]],
                "ref": sup["ref"],
                "pr": sup["pr"],
                "po": sup["po"],
                "confirmed": sup["confirmed"],
                "past_due": sup["past_due"],
                "need_date": f.get("need_date"),
                "ready_date": f.get("ready_date") or _iso(sup["ready_date"]),
                "late_days": f.get("late_days"),
            })
    return lines


def project_row(pid: str, ctx) -> dict:
    fc = ctx["forecast"]["projects"].get(pid, {})
    orders = ctx["snap"].orders_by_project.get(pid, [])
    views = [order_view(o, ctx) for o in orders]
    active = [v for v in views if v["clear_to_build"]["status"] != "complete"]
    open_flags = HotFlag.query.filter(HotFlag.depot_project_id == pid, HotFlag.status != "resolved").count()
    open_quality = sum(1 for o in orders for q in ctx["snap"].notifications.get(o.id, []) if q.closed_at is None)
    lines = acquisition_lines(pid, ctx)
    return {
        "depot_project_id": pid,
        "name": ctx["names"].get(pid),
        "rank": fc.get("rank"),
        "forecast": fc,
        "size": project_size(pid, ctx),
        "orders_active": len(active),
        "orders_clear": sum(1 for v in active if v["clear_to_build"]["status"] in ("clear", "running")),
        "orders_waiting_material": sum(1 for v in active if v["clear_to_build"]["status"] == "waiting_material"),
        "orders_held": sum(1 for v in active if v["clear_to_build"]["status"] == "held"),
        "material_issues": sum(1 for l in lines if not l["consumed"] and l["stage"] not in ("in_stock", "in_house", "in_inspection")),
        "open_quality": open_quality,
        "open_hot_flags": open_flags,
        "issues": project_issues(pid, ctx, views, lines),
        "locations": [
            {"order_number": v["order_number"], "seq": v["current_seq"],
             "work_center": next((o["work_center"] for o in v["operations"] if o["seq"] == v["current_seq"]), None),
             "state": next((o["state"] for o in v["operations"] if o["seq"] == v["current_seq"]), None),
             "dwell_hours": next((o["dwell_hours"] for o in v["operations"] if o["seq"] == v["current_seq"]), None)}
            for v in active
        ],
    }


_OK_STAGES = ("in_stock", "in_house", "in_inspection")


def _d(iso: str | None) -> str:
    """"Oct 6" from an ISO date, for sentences a person reads."""
    return date.fromisoformat(iso).strftime("%b %-d") if iso else "an unknown date"


def _material_fix(line: dict) -> tuple[str, str]:
    """(who, what to do) for one acquisition line: the next step that gets the material moving."""
    po, pr = line["po"] or {}, line["pr"] or {}
    supplier = po.get("supplier") or "the supplier"
    stage = line["stage"]
    if stage == "no_master":
        return "Engineering / master data", (f"Create the S4 material master for {line['material_number']}. It's only "
                                              "on the engineering BOM, so nothing can be requisitioned yet.")
    if stage == "no_pr":
        return "Planner", f"Create a purchase requisition for {line['quantity']:g} {line['unit']}."
    if stage == "pr_created":
        return "PR approver", f"Release PR {pr.get('pr_number')}. Nothing can be ordered until it's released."
    if stage == "pr_released":
        return "Buyer", f"Convert released PR {pr.get('pr_number')} to a purchase order."
    if stage == "rejected":
        return "Quality / Buyer", f"Disposition the rejected receipt on PO {po.get('po_number')} and get replacement stock."
    if line["past_due"]:
        promised = po.get("confirmed_date") or po.get("requested_date")
        return "Buyer", f"Chase {supplier}: PO {po.get('po_number')} was due {_d(promised)} and hasn't been received."
    if stage == "po_placed":
        return "Buyer", (f"Get {supplier} to confirm PO {po.get('po_number')}. It was requested for "
                         f"{_d(po.get('requested_date'))} and isn't confirmed, so that date is a hope, not a promise.")
    if line["late_days"]:
        return "Buyer", (f"Expedite PO {po.get('po_number')} with {supplier}: confirmed {_d(po.get('confirmed_date'))}, "
                         f"needed {_d(line['need_date'])} ({line['late_days']} working days late).")
    return "Buyer", f"Arrives {_d(line['ready_date'])}. Nothing to do unless it slips."


def project_issues(pid: str, ctx, views: list[dict] | None = None, lines: list[dict] | None = None) -> list[dict]:
    """Every problem worth a manager's attention on one project, each with who fixes it, what to
    do, and where in MARTI to see it: material that's short (missing, undated, late, or holding a
    step up right now), MRB holds, open quality notifications, and open hot flags."""
    snap = ctx["snap"]
    views = views if views is not None else [order_view(o, ctx) for o in snap.orders_by_project.get(pid, [])]
    lines = lines if lines is not None else acquisition_lines(pid, ctx)
    waiting_now = {(v["order_number"], m) for v in views for m in v["clear_to_build"].get("missing", [])}
    out = []

    for l in lines:
        if l["consumed"] or l["stage"] in _OK_STAGES:
            continue
        now = (l["order_number"], l["material_number"]) in waiting_now
        if not (now or l["ready_date"] is None or l["late_days"] or l["past_due"]):
            continue
        owner, action = _material_fix(l)
        out.append({
            "kind": "short",
            "title": f"{l['material_number']} {l['description'] or ''}".strip(),
            "detail": (f"{l['stage_label']} · for {l['order_number']} op {l['operation_seq']}"
                       + (" · holding that step up now" if now else "")),
            "owner": owner, "action": action,
            "order_number": l["order_number"], "material_number": l["material_number"],
            "link": "material", "focus": l["material_number"],
        })

    for v in views:
        for op in v["operations"]:
            for q in op["quality"]:
                if not q["open"]:
                    continue
                where = f"{v['order_number']} op {op['seq']} {op['description']} ({op['work_center']})"
                if q["designator"] == "mrb_hold":
                    kind, owner = "held", "MRB (Quality)"
                    action = (f"Disposition QN {q['notification_number']} (use as is, rework, or scrap) so the "
                              f"order can move. Held {round((op['dwell_hours'] or 0) / 24, 1)} days so far.")
                elif q["designator"] == "rework":
                    kind, owner = "quality", op["work_center"]
                    action = f"Finish the rework and close QN {q['notification_number']} when it's confirmed."
                elif q["designator"] == "scrap":
                    kind, owner = "quality", "Planner"
                    action = f"Scrap logged on QN {q['notification_number']}: check whether replacement quantity is needed."
                else:
                    kind, owner = "quality", "Quality"
                    action = f"Review QN {q['notification_number']} and decide whether it needs rework or MRB."
                out.append({
                    "kind": kind,
                    "title": f"{q['description']}",
                    "detail": where,
                    "owner": owner, "action": action,
                    "order_number": v["order_number"], "material_number": None,
                    "link": "routing", "focus": v["order_number"],
                })

    for f in HotFlag.query.filter(HotFlag.depot_project_id == pid, HotFlag.status == "open"):
        out.append({
            "kind": "flag", "title": f.title, "detail": f.detail, "owner": f.owner,
            "action": "Acknowledge it in Hot flags so leadership knows it's being worked.",
            "order_number": None, "material_number": None, "link": "hot-flags", "focus": None,
        })
    return out


def project_size(pid: str, ctx) -> dict:
    """How much work a project still has in front of it, all from S4 routings: parts (production
    orders not yet complete), units, operations, standard hours, and standard hours on the shop's
    current bottleneck. What lets leadership see "1 part, 3 steps" next to "100 parts, 10 steps"."""
    snap, now = ctx["snap"], ctx["now"]
    bottleneck = ctx.get("bottleneck")
    parts = units = ops = 0
    hours = bottleneck_hours = 0.0
    for order in snap.orders_by_project.get(pid, []):
        states = [st for st in scheduler.operation_states(order, snap, now) if st["state"] != "done"]
        if not states:
            continue
        parts += 1
        units += order.quantity
        for st in states:
            ops += 1
            h = scheduler.remaining_hours(st["op"], order.quantity, st["state"])
            hours += h
            if st["op"].work_center == bottleneck:
                bottleneck_hours += h
    return {
        "parts_left": parts,
        "units_left": units,
        "ops_left": ops,
        "std_hours_left": round(hours, 1),
        "bottleneck": bottleneck,
        "bottleneck_hours_left": round(bottleneck_hours, 1),
    }


def project_detail(pid: str, ctx) -> dict:
    orders = ctx["snap"].orders_by_project.get(pid, [])
    flags = HotFlag.query.filter_by(depot_project_id=pid).order_by(HotFlag.raised_at.desc()).all()
    views = [order_view(o, ctx) for o in orders]
    views.sort(key=lambda v: v["clear_to_build"]["status"] == "complete")  # finished orders last
    return {
        **project_row(pid, ctx),
        "orders": views,
        "acquisition": acquisition_lines(pid, ctx),
        "hot_flags": [f.to_dict() for f in flags],
    }


# --- routing tree ----------------------------------------------------------------------------


def project_tree(pid: str, ctx) -> list[dict]:
    """The project's production orders as an assembly tree: an order's children are the orders in
    the same project that make one of its components, to any depth. Each node carries a rollup
    of its whole subtree and a `critical` flag on the chain of orders setting the finish date.

    Parent-child here is matched by material number within the project. In live S4 it would come
    from the superior order (AFKO-MAUFNR) or the reservation's pegging."""
    snap, fc = ctx["snap"], ctx["forecast"]
    orders = snap.orders_by_project.get(pid, [])
    made_here = {o.material_number: o for o in orders}
    views = {o.id: order_view(o, ctx) for o in orders}
    consumed = {c.material_number for o in orders for c in o.components}

    def build(o, seen):
        seen = seen | {o.id}
        kids = []
        for c in o.components:
            child = made_here.get(c.material_number)
            if child is not None and child.id not in seen:
                kids.append(build(child, seen))
        v = views[o.id]
        own = {
            "orders": 1,
            "complete": int(v["clear_to_build"]["status"] == "complete"),
            "ops_done": sum(1 for op in v["operations"] if op["state"] == "done"),
            "ops_total": len(v["operations"]),
            "held": int(v["clear_to_build"]["status"] == "held"),
            "waiting_material": int(v["clear_to_build"]["status"] == "waiting_material"),
            "open_quality": sum(1 for op in v["operations"] for q in op["quality"] if q["open"]),
        }
        rollup = dict(own)
        for k in kids:
            for key in rollup:
                rollup[key] += k["rollup"][key]
        return {**v, "children": kids, "rollup": rollup, "critical": False}

    roots = [build(o, set()) for o in orders if o.material_number not in consumed]

    # Critical chain: the root finishing last (or blocked), then any child whose output gated one
    # of its parent's steps, or that is itself what blocks the parent.
    finish = fc.get("order_finish_day", {})
    live = [r for r in roots if r["clear_to_build"]["status"] != "complete"]
    if live:
        top = max(live, key=lambda r: float("inf") if finish.get(r["order_id"]) is None else finish[r["order_id"]])

        def mark(node):
            node["critical"] = True
            drivers = {fc["operations"].get(op["id"], {}).get("material_driver") for op in node["operations"]}
            for k in node["children"]:
                if k["clear_to_build"]["status"] == "complete":
                    continue
                if k["material_number"] in drivers or (node["forecast_blocked"] and k["forecast_blocked"]):
                    mark(k)

        mark(top)
    roots.sort(key=lambda r: r["clear_to_build"]["status"] == "complete")
    return roots


def acquisition_all(ctx, project_id: str | None = None) -> list[dict]:
    """Acquisition lines for one project or every manufacturing project, in rank order."""
    ids = [project_id] if project_id else ctx["ranking"]
    rank_of = {pid: i for i, pid in enumerate(ctx["ranking"], start=1)}
    return [{**line, "depot_project_id": pid, "project_name": ctx["names"].get(pid), "rank": rank_of.get(pid)}
            for pid in ids for line in acquisition_lines(pid, ctx)]


# --- work centers ----------------------------------------------------------------------------


def constraints(ctx, fc: dict | None = None) -> dict:
    """Work-center view. `fc` is a scenario forecast when Constraints' what-if sandbox is in use;
    queues and history are always today's S4 actuals, only the forward load changes."""
    snap, now = ctx["snap"], ctx["now"]
    fc = fc or ctx["forecast"]
    rank_of = {pid: i for i, pid in enumerate(ctx["ranking"], start=1)}
    by_wc = {code: {"queue": [], "in_process": [], "waits": [], "dwells": []} for code in snap.work_centers}

    for pid, orders in snap.orders_by_project.items():
        for order in orders:
            for st in scheduler.operation_states(order, snap, now):
                op = st["op"]
                bucket = by_wc[op.work_center]
                if st["state"] == "done":
                    if st["wait_hours"] is not None:
                        bucket["waits"].append(st["wait_hours"])
                    if st["dwell_hours"] is not None:
                        bucket["dwells"].append(st["dwell_hours"])
                    continue
                if st["state"] not in ("queued", "on_hold", "in_process"):
                    continue
                item = {
                    "depot_project_id": pid,
                    "project_name": ctx["names"].get(pid),
                    "rank": rank_of.get(pid),
                    "order_number": order.order_number,
                    "seq": op.seq,
                    "description": op.description,
                    "state": st["state"],
                    "arrived_at": _iso(st["arrived_at"]),
                    "dwell_hours": _hours(st["dwell_hours"]),
                    "remaining_hours": _hours(scheduler.remaining_hours(op, order.quantity, st["state"])),
                }
                (bucket["in_process"] if st["state"] == "in_process" else bucket["queue"]).append(item)

    rows = []
    for code, wc in snap.work_centers.items():
        b = by_wc[code]
        cap = wc.capacity_hours_per_day
        queued_hours = sum(i["remaining_hours"] for i in b["queue"])
        wip_hours = queued_hours + sum(i["remaining_hours"] for i in b["in_process"])
        load = fc["work_center_load"].get(code, [])
        caps = fc.get("work_center_capacity", {}).get(code, [cap] * len(load))
        next10 = load[:10]
        rows.append({
            **wc.to_dict(),
            "queue": sorted(b["queue"], key=lambda i: (i["rank"] or 999, -(i["dwell_hours"] or 0))),
            "in_process": b["in_process"],
            "queue_count": len(b["queue"]),
            "queued_hours": _hours(queued_hours),
            "queue_days": round(queued_hours / cap, 1) if cap else None,
            "wip_days": round(wip_hours / cap, 1) if cap else None,
            "oldest_dwell_hours": max((i["dwell_hours"] or 0 for i in b["queue"]), default=None),
            "history_count": len(b["waits"]),
            "median_wait_hours": _hours(median(b["waits"])) if b["waits"] else None,
            "median_dwell_hours": _hours(median(b["dwells"])) if b["dwells"] else None,
            "load_next_10": next10,
            "capacity_next_10": caps[:10],
            "utilization_next_10": round(sum(next10) / sum(caps[:10]), 2) if sum(caps[:10]) else None,
            "wip_hours": _hours(wip_hours),
            "is_bottleneck": code == ctx.get("bottleneck"),
            # People (one 8-hour shift each) needed on top of today's capacity to clear everything
            # waiting or running here within a week.
            "extra_people_to_clear_in_week": advisor.headcount_to_clear(wip_hours, cap),
        })
    rows.sort(key=lambda r: (-(r["wip_days"] or 0), r["code"]))

    blockers = []
    for pid in ctx["ranking"]:
        for line in acquisition_lines(pid, ctx):
            if line["consumed"] or line["stage"] in ("in_stock", "in_house", "in_inspection"):
                continue
            if line["ready_date"] is not None and not line["late_days"] and not line["past_due"]:
                continue
            owner, action = _material_fix(line)
            blockers.append({**line, "depot_project_id": pid, "project_name": ctx["names"].get(pid),
                             "rank": rank_of.get(pid), "owner": owner, "action": action})

    return {"work_centers": rows, "material_blockers": blockers}


# --- triage ----------------------------------------------------------------------------------


def history(limit: int = 20) -> list[dict]:
    return [c.to_dict() for c in PriorityChange.query.order_by(PriorityChange.changed_at.desc()).limit(limit)]
