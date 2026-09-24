"""
Proposals: saved suggestions waiting on a person. A person saves a capacity scenario from
Constraints, and the AI (once connected, see routes/advisor_ai.py) saves re-rank and capacity
proposals. Re-rank proposals are committed through Triage's commit (with `proposal_id`). Capacity
proposals are accepted or dismissed here, as a recorded decision; the capacity itself changes in
S4.
"""

from datetime import date

from flask import Blueprint, jsonify, request

import advisor
import depot_client
import scheduler
import service
from db import db
from models import PROPOSAL_KINDS, PROPOSAL_SOURCES, Proposal, _now

bp = Blueprint("proposals", __name__, url_prefix="/api/proposals")


def validate_levers(levers) -> str | None:
    if not isinstance(levers, list) or not levers:
        return "levers must be a non-empty list"
    for lv in levers:
        t = lv.get("type") if isinstance(lv, dict) else None
        if t not in scheduler.LEVER_TYPES:
            return f"each lever needs a type in {scheduler.LEVER_TYPES}"
        if t in ("add_hours", "add_equipment") and not (lv.get("work_center") and lv.get("hours_per_day")):
            return f"{t} needs work_center and hours_per_day"
        if t == "move_labor" and not (lv.get("from_work_center") and lv.get("to_work_center") and lv.get("hours_per_day")):
            return "move_labor needs from_work_center, to_work_center and hours_per_day"
        if t == "outsource" and not (lv.get("order_number") and lv.get("seq") and lv.get("turnaround_days")):
            return "outsource needs order_number, seq and turnaround_days"
        if t == "expedite_material":
            if not (lv.get("material_number") and lv.get("ready_date")):
                return "expedite_material needs material_number and ready_date"
            try:
                date.fromisoformat(lv["ready_date"])
            except ValueError:
                return "ready_date must be an ISO date (YYYY-MM-DD)"
    return None


@bp.get("")
def list_proposals():
    q = Proposal.query
    if request.args.get("kind") in PROPOSAL_KINDS:
        q = q.filter_by(kind=request.args["kind"])
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    return jsonify({"proposals": [p.to_dict() for p in q.order_by(Proposal.created_at.desc())]})


@bp.post("")
def create_proposal():
    body = request.get_json(force=True) or {}
    kind, source = body.get("kind"), body.get("source") or "person"
    if kind not in PROPOSAL_KINDS or source not in PROPOSAL_SOURCES:
        return jsonify({"error": f"kind must be one of {PROPOSAL_KINDS}, source one of {PROPOSAL_SOURCES}"}), 400
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    if kind == "capacity":
        err = validate_levers(body.get("levers"))
        if err:
            return jsonify({"error": err}), 400
    elif not isinstance(body.get("ranking"), list):
        return jsonify({"error": "a rerank proposal needs a ranking"}), 400
    p = Proposal(kind=kind, source=source, title=title, rationale=body.get("rationale"),
                 ranking=body.get("ranking"), levers=body.get("levers"),
                 created_by=(body.get("created_by") or "").strip() or None)
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


def _decide(proposal_id, status):
    p = db.session.get(Proposal, proposal_id)
    if p is None:
        return jsonify({"error": "proposal not found"}), 404
    if p.status != "open":
        return jsonify({"error": f"proposal is already {p.status}"}), 400
    name = ((request.get_json(force=True, silent=True) or {}).get("name") or "").strip()
    if not name:
        return jsonify({"error": "type your name to record the decision"}), 400
    if status == "accepted" and p.kind != "capacity":
        return jsonify({"error": "re-rank proposals are committed from Triage"}), 400
    p.status, p.decided_by, p.decided_at = status, name, _now()
    db.session.commit()
    posted = 0
    if status == "accepted":
        posted = _journal_capacity_decision(p, name, (request.get_json(force=True, silent=True) or {}).get("person_id"))
    return jsonify({**p.to_dict(), "journal_posted": posted})


def _journal_capacity_decision(p: Proposal, who: str, person_id: str | None) -> int:
    """Journal every project whose forecast finish the accepted levers change, written by code
    from the forecast, never narrated."""
    ctx = service.context()
    fc = scheduler.forecast(ctx["snap"], ctx["ranking"], ctx["need_by"], ctx["today"], ctx["now"], levers=p.levers)
    posted = 0
    for row in advisor.compare(ctx["ranking"], ctx["forecast"], fc, ctx["names"]):
        d = row["finish_delta_days"]
        if not d:
            continue
        text = (f"Capacity decision accepted by {who}: {p.title}. MARTI forecast finish "
                f"{service._d(row['current']['projected_finish'])} → {service._d(row['proposed']['projected_finish'])} "
                f"({'+' if d > 0 else ''}{d} days) once the change is made in S4.")
        if depot_client.post_project_note(row["depot_project_id"], person_id, text):
            posted += 1
    return posted


@bp.post("/<proposal_id>/accept")
def accept(proposal_id):
    return _decide(proposal_id, "accepted")


@bp.post("/<proposal_id>/dismiss")
def dismiss(proposal_id):
    return _decide(proposal_id, "dismissed")
