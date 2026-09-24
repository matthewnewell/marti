"""
Triage: leadership's stack rank of manufacturing projects and each project's need-by date, the
what-if preview that shows the Impact of a proposed re-rank before it's committed, and MARTI's
own suggestions (cut-in checks and better rankings, from advisor.py).

Committing is the only way a ranking changes, and it always takes a person's name and reason. A
commit can carry where the ranking came from (`source`: engine, ai or person, plus the
`proposal_id` when it was a saved proposal), which the history shows as "proposed by ..., committed
by ...".

Every commit also writes a Journal entry (Conway's Depot's shared project journal) on each
project whose rank or forecast changed, authored by the committing persona. The entry is built
by code from the change that was actually applied, never narrated by a model.

Committing also raises hot flags. For every project that moved up, MARTI flags what's actually
in its way right now: material that isn't here in time (to the buyer) and the step sitting in a
queue or on hold (to that work center). A flag is never raised twice for the same blocker while
an earlier one is still open.
"""

from datetime import date

from flask import Blueprint, jsonify, request

import advisor
import depot_client
import scheduler
import service
from db import db
from models import PROPOSAL_SOURCES, HotFlag, PriorityChange, ProjectRank, Proposal, _now

bp = Blueprint("triage", __name__, url_prefix="/api/triage")


def _board(ctx) -> dict:
    return {
        "projects": [service.project_row(pid, ctx) for pid in ctx["ranking"]],
        "history": service.history(),
        "bottleneck": ctx["bottleneck"],
        "depot_reachable": ctx["depot_reachable"],
        "as_of": ctx["forecast"]["as_of"],
    }


def validate_order(order, known) -> str | None:
    if not isinstance(order, list) or not order:
        return "order must be a non-empty list of project ids"
    if len(set(order)) != len(order):
        return "order has duplicate project ids"
    if set(order) != set(known):
        return "order must contain every manufacturing project exactly once"
    return None


@bp.get("")
def get_board():
    return jsonify(_board(service.context()))


@bp.post("/preview")
def preview():
    """Impact of a proposed ranking vs. the current one, per project. Nothing is saved."""
    body = request.get_json(force=True) or {}
    ctx = service.context()
    order = body.get("order")
    err = validate_order(order, ctx["ranking"])
    if err:
        return jsonify({"error": err}), 400
    proposed = scheduler.forecast(ctx["snap"], order, ctx["need_by"], ctx["today"], ctx["now"])
    rows = advisor.compare(order, ctx["forecast"], proposed, ctx["names"])
    return jsonify({"projects": rows, "summary": advisor.summarize(rows)})


@bp.get("/suggestions")
def suggestions():
    """MARTI's own suggestions (engine), plus any open AI re-rank proposals, each with its impact
    freshly forecast. A saved proposal whose project set no longer matches is skipped."""
    ctx = service.context()
    saved = []
    for p in Proposal.query.filter_by(kind="rerank", status="open").order_by(Proposal.created_at.desc()):
        if validate_order(p.ranking, ctx["ranking"]):
            continue
        fc = scheduler.forecast(ctx["snap"], p.ranking, ctx["need_by"], ctx["today"], ctx["now"])
        rows = advisor.compare(p.ranking, ctx["forecast"], fc, ctx["names"])
        saved.append({**p.to_dict(), "impact": rows, "summary": advisor.summarize(rows)})
    return jsonify({
        "cut_in": advisor.cut_in(ctx),
        "rankings": advisor.best_rankings(ctx),
        "proposals": saved,
    })


def _blockers(pid: str, ctx) -> list[dict]:
    """What's in this project's way right now, as hot-flag candidates."""
    out = []
    name = ctx["names"].get(pid) or "this project"
    for line in service.acquisition_lines(pid, ctx):
        if line["consumed"] or line["stage"] in ("in_stock", "in_house", "in_inspection"):
            continue
        late = line["late_days"]
        if line["ready_date"] is not None and not late and not line["past_due"]:
            continue
        if not line["master_exists"]:
            detail = f"No S4 material master yet. {line['order_number']} op {line['operation_seq']} can't be supplied until one exists."
        elif line["stage"] in ("pr_created", "pr_released", "no_pr"):
            detail = f"{line['stage_label']}{' ' + line['ref'] if line['ref'] else ''}. Needed by {line['need_date']} for {line['order_number']} op {line['operation_seq']}."
        else:
            po = line["po"] or {}
            promised = po.get("confirmed_date") or po.get("requested_date")
            detail = (f"PO {line['ref']} ({po.get('supplier') or 'supplier'}) "
                      f"{'confirmed' if po.get('confirmed_date') else 'requested, not confirmed,'} for {promised}; "
                      f"needed {line['need_date']}" + (f", {late} working days late." if late else ", past due."))
        out.append({"target_kind": "material", "target_key": line["material_number"], "owner": "Buyer",
                    "title": f"Expedite {line['material_number']} {line['description'] or ''} for {name}".strip(),
                    "detail": detail})

    for order in ctx["snap"].orders_by_project.get(pid, []):
        view = service.order_view(order, ctx)
        cur = next((o for o in view["operations"] if o["seq"] == view["current_seq"]), None)
        if cur is None or cur["state"] not in ("queued", "on_hold"):
            continue
        dwell = f"{round(cur['dwell_hours'] / 24, 1)} days" if cur["dwell_hours"] is not None else "unknown time"
        if cur["state"] == "on_hold":
            title = f"Disposition MRB hold on {order.order_number} op {cur['seq']}"
            detail = f"{cur['description']} has been held {dwell}. {name} can't be forecast past it."
        else:
            title = f"Pull {order.order_number} op {cur['seq']} forward at {cur['work_center']}"
            detail = f"{cur['description']} has been queued {dwell}."
        out.append({"target_kind": "operation", "target_key": f"{order.order_number}/{cur['seq']}",
                    "owner": cur["work_center"], "title": title, "detail": detail})
    return out


@bp.post("/commit")
def commit():
    body = request.get_json(force=True) or {}
    changed_by = (body.get("changed_by") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not changed_by or not reason:
        return jsonify({"error": "changed_by and reason are both required"}), 400
    source = body.get("source") or "person"
    if source not in PROPOSAL_SOURCES:
        return jsonify({"error": f"source must be one of {PROPOSAL_SOURCES}"}), 400
    proposal = None
    if body.get("proposal_id"):
        proposal = db.session.get(Proposal, body["proposal_id"])
        if proposal is None or proposal.kind != "rerank" or proposal.status != "open":
            return jsonify({"error": "proposal not found or no longer open"}), 400
        source = proposal.source

    ctx = service.context()
    order = body.get("order")
    err = validate_order(order, ctx["ranking"])
    if err:
        return jsonify({"error": err}), 400
    before = list(ctx["ranking"])
    if order == before:
        return jsonify({"error": "ranking is unchanged"}), 400

    rows = {r.depot_project_id: r for r in ProjectRank.query.all()}
    for rank, pid in enumerate(order, start=1):
        if pid in rows:
            rows[pid].rank = rank
        else:
            db.session.add(ProjectRank(depot_project_id=pid, rank=rank))
    person_id = (body.get("person_id") or "").strip() or None
    before_fc, names = ctx["forecast"]["projects"], ctx["names"]
    change = PriorityChange(changed_by=changed_by, reason=reason, before=before, after=order,
                            source=source, proposal_id=proposal.id if proposal else None, person_id=person_id)
    db.session.add(change)
    if proposal is not None:
        proposal.status, proposal.decided_by, proposal.decided_at = "committed", changed_by, _now()
    db.session.flush()

    # Re-read with the new ranking so blockers reflect the new schedule.
    ctx = service.context()
    raised = []
    for pid in order:
        if pid in before and order.index(pid) >= before.index(pid):
            continue
        existing = {f.target_key for f in HotFlag.query.filter(
            HotFlag.depot_project_id == pid, HotFlag.status != "resolved")}
        for b in _blockers(pid, ctx):
            if b["target_key"] in existing:
                continue
            flag = HotFlag(depot_project_id=pid, priority_change_id=change.id, **b)
            db.session.add(flag)
            raised.append(flag)
    db.session.commit()

    posted = 0
    after_fc = ctx["forecast"]["projects"]
    for pid in order:
        text = journal_entry(pid, before_fc[pid], after_fc[pid], names, changed_by, reason, source,
                             sum(1 for f in raised if f.depot_project_id == pid))
        if text and depot_client.post_project_note(pid, person_id, text):
            posted += 1

    return jsonify({"change": change.to_dict(), "hot_flags_raised": [f.to_dict() for f in raised],
                    "journal_posted": posted, **_board(service.context())})


def _fmt(d: str | None) -> str:
    return date.fromisoformat(d).strftime("%b %-d") if d else "no forecast"


def journal_entry(pid, before: dict, after: dict, names: dict, who: str, reason: str, source: str,
                  flags: int) -> str | None:
    """The Journal line for one project after a re-rank, or None if nothing about it changed."""
    moved = before["rank"] != after["rank"]
    finish_moved = before["projected_finish"] != after["projected_finish"] or before["status"] != after["status"]
    if not (moved or finish_moved):
        return None
    name = names.get(pid) or "This project"
    parts = [f"Triage re-rank by {who}"
             + (" (suggested by MARTI's engine)" if source == "engine" else " (suggested by AI)" if source == "ai" else "")
             + (f": {name} moved from #{before['rank']} to #{after['rank']}." if moved else f": {name} stays #{after['rank']}.")]
    parts.append(f"Reason: {reason}")
    if finish_moved:
        status = after["status"].replace("_", " ")
        was = before["status"].replace("_", " ")
        parts.append(f"MARTI forecast finish {_fmt(before['projected_finish'])} → {_fmt(after['projected_finish'])}"
                     + (f", now {status} (was {was})" if status != was else f", {status}")
                     + (f"; need-by {_fmt(after['need_by'])}." if after["need_by"] else "."))
    if flags:
        parts.append(f"{flags} hot flag{'s' if flags != 1 else ''} raised on what's blocking it.")
    return " ".join(parts)


@bp.put("/<depot_project_id>/need-by")
def set_need_by(depot_project_id):
    body = request.get_json(force=True) or {}
    need_by = None
    if body.get("need_by"):
        try:
            need_by = date.fromisoformat(body["need_by"])
        except ValueError:
            return jsonify({"error": "need_by must be an ISO date (YYYY-MM-DD)"}), 400

    row = db.session.get(ProjectRank, depot_project_id)
    if row is None:
        ctx = service.context()
        if depot_project_id not in ctx["names"]:
            return jsonify({"error": "not a manufacturing project MARTI knows about"}), 404
        row = ProjectRank(depot_project_id=depot_project_id, rank=len(ctx["ranking"]) + 1)
        db.session.add(row)
    row.need_by = need_by
    db.session.commit()
    return jsonify(_board(service.context()))
